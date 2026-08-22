import { ingestRawEmail } from "./ingest";

export interface Env {
  PIPELINE_BUCKET: R2Bucket;
}

export default {
  /**
   * Email Routing entry point. Accepts delivery unconditionally: invalid or
   * unexpected messages are preserved as email evidence plus a rejection
   * outcome instead of being bounced back to X-Sense/Gmail.
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
        message_object_key: outcome.message_object_key,
        outcome_object_key: outcome.outcome_object_key,
        attachment_statuses: outcome.attachments.map((attachment) => attachment.status),
      }),
    );
  },
} satisfies ExportedHandler<Env>;
