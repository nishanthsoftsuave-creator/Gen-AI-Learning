# BatchUploader.upload()

`BatchUploader.upload()` uploads a set of local files as a single logical
batch, which is the recommended path any time you have more than a handful
of files to send — it opens a fixed number of parallel connections instead
of one connection per file, which matters a great deal once you're pushing
thousands of small files through a single process. Each file is split into
fixed-size parts before upload; the size of those parts, not the number of
files, is what `chunk_size_mb` controls.

Progress reporting is opt-in. If you don't pass `on_progress`, the upload
still completes normally, it just doesn't emit any progress events, which is
the right default for short-lived scripts and CI jobs where nobody is
watching a progress bar.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| files | list[str] | n/a | Yes |
| chunk_size_mb | int | 8 | No |
| parallelism | int | 4 | No |
| on_progress | callable | None | No |

Raising `parallelism` beyond 4 rarely helps unless you are uploading from a
machine with a very high-bandwidth link, since each additional parallel
stream adds its own TLS overhead. `chunk_size_mb` below 4 increases the
number of round trips per file; above 16 it increases the cost of retrying a
single failed part.

## Example

```python
uploader = client.batch_uploader

def on_progress(event):
    print(f"{event.file}: {event.percent_complete}%")

uploader.upload(
    files=["report_jan.csv", "report_feb.csv", "report_mar.csv"],
    chunk_size_mb=8,
    parallelism=4,
    on_progress=on_progress,
)
```

## Errors

`BatchUploader.upload()` raises `FileNotFoundError` if any path in `files`
does not exist locally, and `PartUploadError` if a single part fails after
its own internal retry budget is exhausted.
