# Reuse existing article attachments

`zammad_add_article` can attach files that already belong to an article in the
same ticket. The server downloads and re-uploads the files; the MCP request and
response contain metadata, not base64 file content.

First obtain the source article ID and its attachment IDs with the existing
read tools. Then pass both reference fields:

```json
{
  "ticket_id": 41,
  "body": "Please see the attached report.",
  "article_type": "email",
  "to": "recipient@example.invalid",
  "source_article_id": 72,
  "attachment_ids": [91, 92]
}
```

The original article fields remain available, including `internal`, `sender`,
`subject`, `cc`, `content_type`, and `time_unit`. Inline `attachments` requests
remain supported. Do not combine inline attachments with references, including
an explicitly empty inline list.

## Validation

- `source_article_id` and `attachment_ids` must be provided together.
- The source article must belong to the target ticket.
- Select between 1 and 10 distinct, strictly positive integer attachment IDs.
  In reference mode, `ticket_id`, `source_article_id`, and attachment IDs reject
  booleans, strings, and floating-point values, including integral floats.
- Every selected attachment must be present on the source article.
- Each file is limited to 10 MiB and the selected files to 25 MiB in total.
  Both limits are inclusive; empty files are allowed.
- Invalid sizes, unsafe filenames, duplicate metadata IDs, and conflicting MIME
  metadata are rejected before downloading.
- Downloaded byte lengths must exactly match the declared sizes.
- Source ownership, selected metadata, and the source update timestamp are read
  again after downloading. A detected change aborts creation.

Files retain their bytes, filenames, and requested order. Two distinct attachment
IDs may have the same filename. When MIME metadata is absent, common PDF, PNG,
JPEG, GIF, and ZIP signatures are recognized; other content uses
`application/octet-stream`. Filenames are not used to guess MIME types.

## Limits and errors

Reference downloads use raw response bytes from the existing authenticated,
resilient HTTP transport, never the SDK's JSON response decoder. The transport
buffers each HTTP response before its length can be checked. These limits
validate accepted uploads; they are **not a hard
memory bound against a dishonest or unexpectedly large download**. Base64
encoding also increases memory use inside the server.

The final read and the create operation are not an atomic transaction. Changes
that happen after the final read, or content changes with unchanged size and
metadata, cannot be excluded.

Reference-mode external read, download, write, and response-conversion errors use generic messages
instead of including API response bodies or file content. A write is attempted
once. Article creation is non-idempotent and may send an email: do not retry
an uncertain failure automatically. Check the target ticket before deciding
whether another create operation is appropriate.
