import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user


@pytest.mark.anyio # 运行异步测试函数(必须有这个)
# “当系统里一个 Post 都没有时，调用 /api/posts 应该正常返回 200，
# 并明确告诉我现在有 0 个帖子、没有更多数据。”
async def test_get_posts_empty(client: AsyncClient):
    # 请求获得路径
    response = await client.get("/api/posts")

    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


@pytest.mark.anyio
async def test_get_post_not_found(client: AsyncClient):
    response = await client.get("/api/posts/999")
    # 检查 HTTP 状态码是不是 404 Not Found
    assert response.status_code == 404
    # 检查 FastAPI 返回的 JSON 错误信息是不是
    assert response.json()["detail"] == "Post not found"
    # 所以两行合起来就是：
    # 不仅要求接口返回 404，还要求返回的错误原因必须是 "Post not found"。

# assert类似于if,但是if失败了不代表测试失败
# 而assert是检查条件，如果不满足一个则代表测试失败

@pytest.mark.anyio
async def test_create_post_success(client: AsyncClient):
    # 认证阶段
    user = await create_test_user(client)# 创建用户
    token = await login_user(client) # 用户登录后，获取token
    headers = auth_header(token)

    response = await client.post(
        "/api/posts",
        json={"title": "My First Post", "content": "This is the content"},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My First Post"
    assert data["content"] == "This is the content"
    assert data["user_id"] == user["id"]
    assert "id" in data
    assert "date_posted" in data
    assert data["author"]["username"] == "testuser"


@pytest.mark.anyio
async def test_create_post_unauthorized(client: AsyncClient):
    response = await client.post(
        "/api/posts",
        json={"title": "Test Post", "content": "Test content"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_update_post_success(client: AsyncClient):
    # 创建用户，登录
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    # 创建帖子
    response = await client.post(
        "/api/posts",
        json={"title": "Original Title", "content": "Original content"},
        headers=headers,
    )
    post_id = response.json()["id"]

    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Updated Title"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["content"] == "Original content"


@pytest.mark.anyio
async def test_update_post_wrong_user(client: AsyncClient):
    await create_test_user(client, username="user1", email="user1@example.com")
    token1 = await login_user(client, email="user1@example.com")
    
    # 使用user1的token创建一个帖子
    response = await client.post(
        "/api/posts",
        json={"title": "User 1's Post", "content": "Only user 1 can edit this"},
        headers=auth_header(token1),
    )
    post_id = response.json()["id"]


    await create_test_user(client, username="user2", email="user2@example.com")
    token2 = await login_user(client, email="user2@example.com")
    # 尝试更新,(user2)使用patch来对user1的帖子进行操作
    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "Hacked Title"},
        headers=auth_header(token2),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this post"


@pytest.mark.anyio
async def test_get_posts_with_pagination(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    for i in range(5):
        response = await client.post(
            "/api/posts",
            json={"title": f"Post {i}", "content": f"Content for post {i}"},
            headers=headers,
        )
        assert response.status_code == 201

    # 创建5个帖子后
    response = await client.get("/api/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 5
    assert data["has_more"] is False

    # 给我最多2个帖子
    response = await client.get("/api/posts?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["has_more"] is True

    response = await client.get("/api/posts?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["posts"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2
