import PostalMime, { type Email } from "postal-mime";

/**
 * Email-to-R2 ingest core.
 *
 * Writes the exact same object-key layout and manifest shape as the Python
 * batch parser (src/basement_analysis/raw_email_ingest.py) so hosted and
 * local ingest are interchangeable:
 *
 *   raw-emails/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<sha>.eml
 *   csv/source=x-sense/export_date=YYYY-MM-DD/attachment_sha256=<sha>/<safe_filename>.csv
 *   manifests/ingest/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<sha>.json
 *   manifests/rejections/source=x-sense/received_date=YYYY-MM-DD/raw_sha256=<sha>.json
 */

export const PARSER_VERSION = "basement_email_ingest_worker.v1";
export const SOURCE = "x-sense";
export const ACCEPTED_SUBJECT =
  "Your Temperature and Relative Humidity Data Export (Please Do Not Reply)";
export const EXPECTED_CSV_ATTACHMENT_COUNT = 3;
export const REQUIRED_SENSOR_COLUMNS = [
  "Time",
  "Temperature_Celsius",
  "Relative Humidity_Percent",
] as const;

export type EmailStatus =
  | "accepted"
  | "duplicate_raw_sha256"
  | "invalid_raw_email"
  | "subject_mismatch"
  | "no_csv_attachments"
  | "unexpected_csv_attachment_count"
  | "invalid_csv_attachments";

export type AttachmentStatus =
  | "extracted"
  | "duplicate_content_hash"
  | "invalid_csv"
  | "skipped";

export interface AttachmentOutcome {
  filename: string;
  content_sha256: string;
  status: AttachmentStatus;
  row_count: number;
  reason: string;
  csv_object_key: string | null;
}

export interface IngestOutcome {
  status: EmailStatus;
  reason: string;
  raw_object_key: string;
  raw_sha256: string;
  manifest_object_key: string;
  attachments: AttachmentOutcome[];
  validation_errors: string[];
}

interface CsvValidation {
  status: "valid" | "invalid_csv";
  rowCount: number;
  reason: string;
  exportDate: string | null;
}

interface CsvCandidate {
  filename: string;
  content: Uint8Array;
}

export async function ingestRawEmail(
  rawBytes: Uint8Array,
  bucket: R2Bucket,
  now: Date = new Date(),
): Promise<IngestOutcome> {
  const rawSha256 = await sha256Hex(rawBytes);

  let email: Email | null = null;
  let parseError = "";
  try {
    email = await PostalMime.parse(copyBytes(rawBytes));
  } catch (error) {
    parseError = `could not parse raw email: ${String(error)}`;
  }

  const receivedDate = email === null ? utcDate(now) : receivedDateFor(email, now);
  const rawObjectKey =
    `raw-emails/source=${SOURCE}/received_date=${receivedDate}/raw_sha256=${rawSha256}.eml`;

  if ((await bucket.head(rawObjectKey)) !== null) {
    return {
      status: "duplicate_raw_sha256",
      reason: "raw email bytes already stored under this content-addressed key",
      raw_object_key: rawObjectKey,
      raw_sha256: rawSha256,
      manifest_object_key: manifestObjectKey("ingest", receivedDate, rawSha256),
      attachments: [],
      validation_errors: [],
    };
  }

  await putIfAbsent(bucket, rawObjectKey, copyBytes(rawBytes), "message/rfc822");

  if (email === null) {
    return writeRejection(bucket, {
      status: "invalid_raw_email",
      reason: parseError,
      rawObjectKey,
      rawSha256,
      receivedDate,
      headers: {},
      attachments: [],
      validationErrors: [parseError],
    });
  }

  const headers = selectedHeaders(email, rawSha256);
  const candidates = csvAttachmentCandidates(email);
  const validationErrors: string[] = [];

  const subject = (email.subject ?? "").trim();
  if (subject !== ACCEPTED_SUBJECT) {
    validationErrors.push(`subject does not match accepted X-Sense pattern: ${subject}`);
  }
  if (candidates.length === 0) {
    validationErrors.push("message contained no CSV attachments");
  } else if (candidates.length !== EXPECTED_CSV_ATTACHMENT_COUNT) {
    validationErrors.push(
      `expected ${EXPECTED_CSV_ATTACHMENT_COUNT} CSV attachments, found ${candidates.length}`,
    );
  }

  const validations = await Promise.all(
    candidates.map(async (candidate) => ({
      candidate,
      contentSha256: await sha256Hex(candidate.content),
      validation: validateSensorCsv(candidate.content),
    })),
  );
  for (const { candidate, validation } of validations) {
    if (validation.status !== "valid") {
      validationErrors.push(`invalid CSV attachment ${candidate.filename}: ${validation.reason}`);
    } else if (validation.exportDate === null) {
      validationErrors.push(
        `invalid CSV attachment ${candidate.filename}: could not derive export date from the first Time value`,
      );
    }
  }

  if (validationErrors.length > 0) {
    const status: EmailStatus =
      subject !== ACCEPTED_SUBJECT
        ? "subject_mismatch"
        : candidates.length === 0
          ? "no_csv_attachments"
          : candidates.length !== EXPECTED_CSV_ATTACHMENT_COUNT
            ? "unexpected_csv_attachment_count"
            : "invalid_csv_attachments";
    return writeRejection(bucket, {
      status,
      reason: validationErrors[0],
      rawObjectKey,
      rawSha256,
      receivedDate,
      headers,
      attachments: validations.map(({ candidate, contentSha256, validation }) => ({
        filename: candidate.filename,
        content_sha256: contentSha256,
        status: validation.status === "valid" ? "skipped" : "invalid_csv",
        row_count: validation.rowCount,
        reason:
          validation.status === "valid"
            ? "valid CSV in rejected email; not extracted"
            : validation.reason,
        csv_object_key: null,
      })),
      validationErrors,
    });
  }

  const attachments: AttachmentOutcome[] = [];
  for (const { candidate, contentSha256, validation } of validations) {
    const csvObjectKey =
      `csv/source=${SOURCE}/export_date=${validation.exportDate}/` +
      `attachment_sha256=${contentSha256}/${safeFilename(candidate.filename)}`;
    const written = await putIfAbsent(bucket, csvObjectKey, copyBytes(candidate.content), "text/csv");
    attachments.push({
      filename: candidate.filename,
      content_sha256: contentSha256,
      status: written ? "extracted" : "duplicate_content_hash",
      row_count: validation.rowCount,
      reason: written
        ? "first-seen valid CSV content"
        : "valid CSV bytes already extracted from another email",
      csv_object_key: written ? csvObjectKey : null,
    });
  }

  const manifestKey = manifestObjectKey("ingest", receivedDate, rawSha256);
  const outcome: IngestOutcome = {
    status: "accepted",
    reason: "processed CSV attachment candidates",
    raw_object_key: rawObjectKey,
    raw_sha256: rawSha256,
    manifest_object_key: manifestKey,
    attachments,
    validation_errors: [],
  };
  await putIfAbsent(
    bucket,
    manifestKey,
    manifestJson(outcome, headers, receivedDate),
    "application/json",
  );
  return outcome;
}

interface RejectionInput {
  status: EmailStatus;
  reason: string;
  rawObjectKey: string;
  rawSha256: string;
  receivedDate: string;
  headers: Record<string, string>;
  attachments: AttachmentOutcome[];
  validationErrors: string[];
}

async function writeRejection(bucket: R2Bucket, input: RejectionInput): Promise<IngestOutcome> {
  const manifestKey = manifestObjectKey("rejections", input.receivedDate, input.rawSha256);
  const outcome: IngestOutcome = {
    status: input.status,
    reason: input.reason,
    raw_object_key: input.rawObjectKey,
    raw_sha256: input.rawSha256,
    manifest_object_key: manifestKey,
    attachments: input.attachments,
    validation_errors: input.validationErrors,
  };
  await putIfAbsent(
    bucket,
    manifestKey,
    manifestJson(outcome, input.headers, input.receivedDate),
    "application/json",
  );
  return outcome;
}

function manifestObjectKey(
  kind: "ingest" | "rejections",
  receivedDate: string,
  rawSha256: string,
): string {
  return `manifests/${kind}/source=${SOURCE}/received_date=${receivedDate}/raw_sha256=${rawSha256}.json`;
}

function manifestJson(
  outcome: IngestOutcome,
  headers: Record<string, string>,
  receivedDate: string,
): string {
  const manifest: Record<string, unknown> = {
    attachments: outcome.attachments,
    headers,
    parser_version: PARSER_VERSION,
    raw_object_key: outcome.raw_object_key,
    raw_sha256: outcome.raw_sha256,
    reason: outcome.reason,
    received_date: receivedDate,
    source: SOURCE,
    status: outcome.status,
  };
  if (outcome.validation_errors.length > 0) {
    manifest.validation_errors = outcome.validation_errors;
  }
  return stableJson(manifest);
}

/** JSON with lexicographically sorted keys and 2-space indent, like Python's
 * json.dumps(..., indent=2, sort_keys=True). */
function stableJson(value: unknown): string {
  const sortValue = (input: unknown): unknown => {
    if (Array.isArray(input)) {
      return input.map(sortValue);
    }
    if (input !== null && typeof input === "object") {
      const entries = Object.entries(input as Record<string, unknown>);
      entries.sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0));
      return Object.fromEntries(entries.map(([key, item]) => [key, sortValue(item)]));
    }
    return input;
  };
  return JSON.stringify(sortValue(value), null, 2);
}

function csvAttachmentCandidates(email: Email): CsvCandidate[] {
  const candidates: CsvCandidate[] = [];
  for (const attachment of email.attachments) {
    const filename = attachment.filename ?? "";
    const isCsvFilename = filename.toLowerCase().endsWith(".csv");
    const isCsvMimeType = attachment.mimeType === "text/csv";
    if (!isCsvFilename && !isCsvMimeType) {
      continue;
    }
    candidates.push({
      filename: filename || "attachment.csv",
      content: attachmentBytes(attachment.content),
    });
  }
  return candidates;
}

function attachmentBytes(content: ArrayBuffer | Uint8Array | string): Uint8Array {
  if (typeof content === "string") {
    return new TextEncoder().encode(content);
  }
  if (content instanceof Uint8Array) {
    return content;
  }
  return new Uint8Array(content);
}

export function validateSensorCsv(content: Uint8Array): CsvValidation {
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false }).decode(content);
  } catch (error) {
    return {
      status: "invalid_csv",
      rowCount: 0,
      reason: `cannot decode as utf-8: ${String(error)}`,
      exportDate: null,
    };
  }
  if (text.charCodeAt(0) === 0xfeff) {
    text = text.slice(1);
  }

  const lines = text.split(/\r\n|\r|\n/).filter((line) => line.length > 0);
  if (lines.length === 0) {
    return {
      status: "invalid_csv",
      rowCount: 0,
      reason: `missing required columns: ${REQUIRED_SENSOR_COLUMNS.join(", ")}`,
      exportDate: null,
    };
  }

  const fieldnames = lines[0].split(",");
  const missingColumns = REQUIRED_SENSOR_COLUMNS.filter(
    (column) => !fieldnames.includes(column),
  );
  if (missingColumns.length > 0) {
    return {
      status: "invalid_csv",
      rowCount: 0,
      reason: `missing required columns: ${missingColumns.join(", ")}`,
      exportDate: null,
    };
  }

  let rowCount = 0;
  let exportDate: string | null = null;
  for (const line of lines.slice(1)) {
    rowCount += 1;
    const values = line.split(",");
    const row = new Map(fieldnames.map((name, index) => [name, values[index] ?? ""]));
    if (exportDate === null) {
      exportDate = parseExportDate(row.get("Time"));
    }
    for (const column of REQUIRED_SENSOR_COLUMNS) {
      if (!row.get(column)) {
        return {
          status: "invalid_csv",
          rowCount,
          reason: `row ${rowCount} has blank required column ${column}`,
          exportDate,
        };
      }
    }
  }
  return { status: "valid", rowCount, reason: "valid sensor CSV", exportDate };
}

/** Accepts the same first-Time-value formats as the Python parser. */
export function parseExportDate(rawTime: string | undefined): string | null {
  if (!rawTime) {
    return null;
  }
  const patterns = [
    /^(\d{4})\/(\d{2})\/(\d{2}) \d{2}:\d{2}$/,
    /^(\d{4})-(\d{2})-(\d{2}) \d{2}:\d{2}:\d{2}$/,
    /^(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}$/,
  ];
  for (const pattern of patterns) {
    const match = rawTime.match(pattern);
    if (match !== null && isRealDate(match[1], match[2], match[3])) {
      return `${match[1]}-${match[2]}-${match[3]}`;
    }
  }
  return null;
}

function isRealDate(year: string, month: string, day: string): boolean {
  const parsed = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  return (
    parsed.getUTCFullYear() === Number(year) &&
    parsed.getUTCMonth() === Number(month) - 1 &&
    parsed.getUTCDate() === Number(day)
  );
}

function receivedDateFor(email: Email, now: Date): string {
  const dateHeader = email.date;
  if (dateHeader) {
    const parsed = new Date(dateHeader);
    if (!Number.isNaN(parsed.getTime())) {
      return utcDate(parsed);
    }
  }
  return utcDate(now);
}

function utcDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function selectedHeaders(email: Email, rawSha256: string): Record<string, string> {
  const rawHeader = (key: string): string =>
    email.headers.find((header) => header.key === key)?.value ?? "";
  const messageId = (email.messageId ?? "").trim();
  return {
    message_id: messageId || `missing-message-id:${rawSha256}`,
    date: rawHeader("date"),
    from: rawHeader("from"),
    to: rawHeader("to"),
    subject: rawHeader("subject"),
  };
}

export function safeFilename(filename: string): string {
  const cleaned = filename.replace(/[^A-Za-z0-9._-]/g, "_");
  return cleaned || "attachment.csv";
}

/** Create-if-absent via head-then-put; R2 reads are strongly consistent. */
async function putIfAbsent(
  bucket: R2Bucket,
  key: string,
  value: Uint8Array<ArrayBuffer> | string,
  contentType: string,
): Promise<boolean> {
  if ((await bucket.head(key)) !== null) {
    return false;
  }
  await bucket.put(key, value, { httpMetadata: { contentType } });
  return true;
}

export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", copyBytes(bytes));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function copyBytes(bytes: Uint8Array): Uint8Array<ArrayBuffer> {
  const copy = new Uint8Array(new ArrayBuffer(bytes.byteLength));
  copy.set(bytes);
  return copy;
}
