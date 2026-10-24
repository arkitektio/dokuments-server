"""Files reach dokuments through arkitekt-datalayer, against the stack's real RustFS.

A grant is an STS session scoped to one key; the file is written with it, finished, then filed.
Everything is the organization's: another organization's store, file, document or page is not
found.
"""

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError

from dokuments_server.schema import schema

REQUEST = "mutation($name: String!, $size: ByteCount) { requestMediaUpload(input: {originalFileName: $name, fileSize: $size}) { accessKey secretKey sessionToken bucket key store } }"
FINISH = "mutation($id: String!) { finishMediaUpload(input: {storeId: $id}) { id sizeBytes } }"
FILE = "mutation($file: FileLike!) { fromFileLike(input: {file: $file}) { id name store { id key } } }"
ACCESS = "mutation($id: String!) { requestMediaAccess(input: {storeId: $id}) { accessKey secretKey sessionToken bucket key } }"
GET_FILE = "query($id: ID!) { file(id: $id) { id name } }"


def _grant_client(grant: dict, endpoint: str):  # noqa: ANN202
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=grant["accessKey"],
        aws_secret_access_key=grant["secretKey"],
        aws_session_token=grant["sessionToken"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


async def _execute(context, query: str, variables: dict, allow_errors: bool = False):  # noqa: ANN001, ANN202
    result = await schema.execute(query, variable_values=variables, context_value=context)
    if not allow_errors:
        assert not result.errors, result.errors
    return result


async def _upload(context, endpoint: str, body: bytes, name: str = "report.pdf") -> str:  # noqa: ANN001
    grant = (await _execute(context, REQUEST, {"name": name, "size": len(body)})).data["requestMediaUpload"]
    _grant_client(grant, endpoint).put_object(Bucket=grant["bucket"], Key=grant["key"], Body=body)
    finished = (await _execute(context, FINISH, {"id": grant["store"]})).data["finishMediaUpload"]
    assert finished["sizeBytes"] == len(body)
    return grant["store"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_file_is_uploaded_finished_and_filed(authenticated_context, s3_endpoint):
    body = b"%PDF-1.4 not really a pdf, but bytes are bytes"
    store = await _upload(authenticated_context, s3_endpoint, body)

    file = (await _execute(authenticated_context, FILE, {"file": store})).data["fromFileLike"]
    assert file["name"] == "report.pdf" and file["store"]["id"] == store

    access = (await _execute(authenticated_context, ACCESS, {"id": store})).data["requestMediaAccess"]
    assert _grant_client(access, s3_endpoint).get_object(Bucket=access["bucket"], Key=access["key"])["Body"].read() == body


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_grant_writes_only_its_own_key(authenticated_context, s3_endpoint):
    grant = (await _execute(authenticated_context, REQUEST, {"name": "a.pdf"})).data["requestMediaUpload"]
    s3 = _grant_client(grant, s3_endpoint)
    with pytest.raises(ClientError):
        s3.put_object(Bucket=grant["bucket"], Key="someone-else", Body=b"x")
    s3.put_object(Bucket=grant["bucket"], Key=grant["key"], Body=b"abc")


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_unfinished_upload_cannot_be_filed(authenticated_context, s3_endpoint):
    grant = (await _execute(authenticated_context, REQUEST, {"name": "a.pdf"})).data["requestMediaUpload"]
    refused = await _execute(authenticated_context, FILE, {"file": grant["store"]}, allow_errors=True)
    assert refused.errors and "has not been finished" in refused.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_another_organization_sees_neither_the_store_nor_the_file(authenticated_context, other_org_context, s3_endpoint):
    store = await _upload(authenticated_context, s3_endpoint, b"mine")
    file = (await _execute(authenticated_context, FILE, {"file": store})).data["fromFileLike"]

    assert (await _execute(other_org_context, FILE, {"file": store}, allow_errors=True)).errors
    assert (await _execute(other_org_context, ACCESS, {"id": store}, allow_errors=True)).errors
    assert (await _execute(other_org_context, GET_FILE, {"id": file["id"]}, allow_errors=True)).errors
    assert (await _execute(authenticated_context, GET_FILE, {"id": file["id"]})).data["file"]["id"] == file["id"]
