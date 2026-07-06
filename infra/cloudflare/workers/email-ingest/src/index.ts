import { ingestRawEmail } from "./ingest";

export interface Env {
  PIPELINE_BUCKET: R2Bucket;
}

export default {
  /**
   * Email Routing entry point. Accepts delivery unconditionally: invalid or
   * unexpected messages are preserved as raw .eml evidence plus a rejection
   * manifest instead of being bounced back to X-Sense/Gmail.
   */
  async email(message: ForwardableEmailMessage, env: Env): Promise<void> {
    const rawBytes = new Uint8Array(await new Response(message.raw).arrayBuffer());
    const outcome = await ingestRawEmail(rawBytes, env.PIPELINE_BUCKET);
    console.log(
      JSON.stringify({
        event: "email_ingest",
        from: message.from,
        to: message.to,
        status: outcome.status,
        reason: outcome.reason,
        raw_object_key: outcome.raw_object_key,
        manifest_object_key: outcome.manifest_object_key,
        attachment_statuses: outcome.attachments.map((attachment) => attachment.status),
      }),
    );
  },
} satisfies ExportedHandler<Env>;
