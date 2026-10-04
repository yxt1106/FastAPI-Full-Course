from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
# T4: BaseModel: pydantic的基类，用于定义数据模型
# ConfigDict: 用于配置模型的行为和属性
# EmailStr: 用于验证电子邮件地址的字段类型。
# 例如: "user@example.com"

# Field: 用于定义模型字段的属性和验证规则
# 例如: Field(min_length=1, max_length=50) 表示该字段的最小长度为1，最大长度为50

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120) # EmailStr默认不会为空

# 注册用户时的数据
class UserCreate(UserBase):
    password: str = Field(min_length=8)

# 公开返回给客户端的用户信息: 比如用户发的贴子
class UserPublic(BaseModel):
    # ConfigDict(from_attributes=True): 允许从SQLAlchemy模型实例中获取数据，而不仅仅是从字典中获取数据
    # from_attributes=True： pyantic可以从SQLAlchemy模型实例中获取数据，而不仅仅是从字典中获取数据
    
    # 举个例子。
    # SQLAlchemy：user = User(id=1, username="Tom",image_file="abc.jpg")
    # 这是一个：SQLAlchemy User 对象, 但 FastAPI 的响应模型是：
    # UserPublic了from_attributes=True

    # 就可以把：
    # SQLAlchemy User
    #         ↓
    # Pydantic UserPublic
    # 转换过去。

    # 大概相当于：user.id, user.username, user.image_file, user.image_path

    # 分别填进：UserPublic.id,UserPublic.username,UserPublic.image_file
    # UserPublic.image_path
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    image_file: str | None
    image_path: str


class UserPrivate(UserPublic):
    email: EmailStr # 邮箱格式


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)


class Token(BaseModel):
    access_token: str
    token_type: str

# PostBase: 定义了一个基础的帖子模型，包含标题和内容字段。
class PostBase(BaseModel):
    # Field(min_length=1, max_length=100): 定义了标题字段的最小长度为1，最大长度为100。
    # Field(min_length=1): 定义了内容字段的最小长度为1
    # Field(max_length=100): 定义了电子邮件字段的最大长度为100
    # constraints约束: 定义字段的约束条件，例如最小长度、最大长度等。
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)


class PostCreate(PostBase): # 表示继承于 PostBase 类，表示创建帖子时需要提供的字段。
    # 不用user_id:int: 因为 user_id 不再由前端提交，
    # 而是由后端根据当前登录用户 current_user.id 自动确定。
    # 这样客户端没办法宣称自己是其他人了
    pass 
    # pass： 表示占位符，表示该类没有额外的字段或方法。
    # 相当于一个空类，继承了 PostBase 的所有字段和验证规则。


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1)


# PostResponse: 定义了一个帖子响应模型，继承自 PostBase 类，并添加了额外的字段，如 id、user_id、date_posted 和 author。
class PostResponse(PostBase):
    # model_config = ConfigDict(from_attributes=True) 
    # model_config: 用于配置模型的行为和属性。
    # from_attributes=True 表示从对象的属性中获取数据，而不仅从字典中获取数据。
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    date_posted: datetime
    author: UserPublic


class PaginatedPostsResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=120)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
