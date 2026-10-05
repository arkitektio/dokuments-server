# dokuments-server

The document service of an [Arkitekt](https://arkitekt.live) hub. It stores uploaded files,
the documents made from them, and each document's pages with their image and recognized
text. It does no OCR itself: an app reads a file, splits and recognizes it, and writes the
pages back here. It is registered as `live.arkitekt.dokuments` and has a python client,
[`dokuments`](https://pypi.org/project/dokuments/).

## What it stores

| Concept | What it is |
| --- | --- |
| `File` | An uploaded file in the object store, owned by an organization. |
| `Document` | A file read as a document: its title, and when it was processed. |
| `Page` | One page of a document: its index, its image in the object store, its text, and the raw OCR result (text lines) that text was taken from. |
| `Dataset` | A folder of files. |

The file and page bytes live in an S3 object store; Postgres holds the rows that point at
them.

## API

GraphQL is served at `/graphql` (HTTP and WebSocket), with the SDL at `/schema`.

| Operations | What they do |
| --- | --- |
| `requestFileUpload`, `requestFileUploadPresigned` | Hand out credentials to upload a file straight to the object store. |
| `fromFileLike` | Register the uploaded object as a `File`. |
| `requestFileAccess` | Hand out credentials to read a file. |
| `createDocument`, `createPage` | Record a document for a file, and a page with its text and OCR result. |
| `deleteFile` | Delete a file. |
| `files`, `documents`, `pages` (and one by id) | The stored rows. |
| `files` (subscription) | File updates as they happen. |

## Hub integration

Declared in [`dokuments_server/contract.py`](dokuments_server/contract.py):

- **Scopes**: `dokuments_read`, `dokuments_write`.
- **Needs**: `media` storage, tokens issued by lok.

It has no peers: it does not register with rekuest and offers no actions.

## Running

The image is `jhnnsrs/dokuments`. It has no default command, and starting it takes two steps:

```sh
python -m arkitekt_service migrate   # wait for the database, apply migrations, run setup
bash run.sh                          # serve on :80 (daphne), and nothing else
```

`run-debug.sh` does both in one go with Django's autoreloading server, for development.

It needs Postgres, Redis and an S3 object store (RustFS in a standard deployment).

## Configuration

The service reads `config.yaml`, or the file named by `ARKITEKT_CONFIG_FILE`; any value can
be overridden by an environment variable (`POSTGRES__HOST`). `python manage.py
validate_settings` prints the configuration as the service reads it, with secrets redacted.

See [CONFIG.md](CONFIG.md) for every value.

## Development

```sh
uv sync
uv run pytest
```

The suite runs against a real stack, brought up by [dokker](https://github.com/jhnnsrs/dokker)
from `tests/integration/docker-compose.yaml`: Postgres (`jhnnsrs/daten:next`), RustFS with
its buckets created by `jhnnsrs/init:next`, and Redis, on ports Docker picks. It needs a
running Docker daemon. The fixtures are in the repo-root `conftest.py`, so the tests under
`core/tests/` use the same stack.

## Releases

Releases are tags: a push to `main` cuts a stable version, a push to `next` a release
candidate. Each one publishes `jhnnsrs/dokuments` under its version (`X.Y.Z`, `X.Y`, `X`),
plus `latest` from `main` and `next` from `next`. The `version` in `pyproject.toml` is a
placeholder. Release notes are on
[GitHub Releases](https://github.com/arkitektio/dokuments-server/releases).
