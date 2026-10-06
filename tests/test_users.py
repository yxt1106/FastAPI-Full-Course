from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user

# 
@pytest.mark.anyio
async def test_create_user_validation_error(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "testuser",
        },
    )

    assert response.status_code == 422
    assert "email" in response.text
    assert "password" in response.text


@pytest.mark.anyio
async def test_create_user_duplicate_email(client: AsyncClient):
    await create_test_user(client) # 使用默认值创建用户

    response = await client.post( 
        # 创建另一个用户,但是使用同一个邮箱
        "/api/users",
        json={
            "username": "different_user",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    # 此时应该报错,因为一个邮箱只能注册一个账号
    # 对报错部分进行检查
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.anyio # 用户创建成功的情况
async def test_create_user_success(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepassword123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "image_path" in data
    assert "password" not in data
    assert "password_hash" not in data

# 参数里的mocked_aws: 固定产生的S3客户端
@pytest.mark.anyio # 更新用户头像测试
async def test_upload_profile_picture(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)

    # 从磁盘中读取图像
    test_image_path = Path(__file__).parent / "test_image.jpg"
    image_bytes = test_image_path.read_bytes() # 读取图像字节

    response = await client.patch(# 关于图像上传的响应
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", BytesIO(image_bytes), "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"] is not None
    assert data["image_file"].endswith(".jpg")
    assert "s3" in data["image_path"]

    # 使用mocked的S3客户都安来验证文件实际上存在mocked S3桶里
    s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket")
    assert "Contents" in s3_objects
    assert len(s3_objects["Contents"]) == 1
    assert s3_objects["Contents"][0]["Key"].endswith(data["image_file"])
    # 不仅测试响应,也测试响应到来的副作用


@pytest.mark.anyio # 密码重置邮件的测试
async def test_forgot_password_sends_email(client: AsyncClient):
    await create_test_user(client)

    # 测试“忘记密码”接口时，不真的发送邮件，
    # 而是把发送邮件的函数临时替换成一个 Mock，
    # 然后调用接口，检查邮件发送逻辑有没有被正确触发。
    with patch(# 作为mock发送
        # send_password_reset_email在email_utils里
        # 当routers_users.py从email_utils导入这个
        # send_password_reset_email函数时,
        # 这不会创建真正的链接到email.utils
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,# 邮件函数是异步的
    ) as mock_send:
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 202
        mock_send.assert_awaited_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to_email"] == "test@example.com"
        assert call_kwargs["username"] == "testuser"
        assert "token" in call_kwargs
