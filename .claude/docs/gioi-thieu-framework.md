# Giới thiệu Xime Framework

## 1. Mục tiêu

Xime là một Python backend framework được xây dựng nhằm đơn giản hóa việc phát triển các hệ thống theo:

- Clean Architecture
- Domain Driven Design (DDD)
- Modular Monolith
- Microservice

Xime không cố gắng thay thế các thư viện nền tảng phổ biến của Python. Thay vào đó, Xime cung cấp một tầng kiến trúc phía trên các thư viện này để giảm boilerplate, chuẩn hóa cấu trúc dự án và tự động hóa việc quản lý dependency.

---

## 2. Thư viện kế thừa

Xime không viết lại các thành phần nền tảng đã được cộng đồng kiểm chứng. Framework tận dụng:

### FastAPI

- HTTP Server, Routing, OpenAPI, Swagger UI
- Middleware, Lifespan
- Request Parsing, Response Serialization
- Security Integration

### Dependency Injector

Nền tảng DI runtime của Xime:

```python
providers.Singleton(...)
providers.Factory(...)
providers.Resource(...)
```

Chịu trách nhiệm: Singleton/Factory/Resource Provider, Dependency Graph Runtime, Async Resource Management, Dependency Override cho Testing.

### Pydantic

- Validation, Serialization
- Configuration Binding
- DTO Definition

---

## 3. Vai trò của Xime

Xime hoạt động như một tầng phía trên Dependency Injector:

```text
Application Code
        ↓
      Xime
        ↓
Dependency Injector
        ↓
Python Objects
```

Xime chịu trách nhiệm: Package Scanning, Dependency Discovery, Type Hint Resolution, Interface Resolution, Auto Registration, Convention System, Configuration System, Lifecycle Integration.

Developer không cần viết:

```python
providers.Singleton(UserService, repository=user_repository)
```

Thay vào đó chỉ cần khai báo constructor:

```python
class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository
```

Xime tự động: Scan → Resolve → Register → Instantiate.

---

## 4. Triết lý DI

Mục tiêu không phải tạo DI Container mới, mà là tận dụng Dependency Injector nhưng loại bỏ phần cấu hình thủ công. Developer không cần làm việc với `providers.Singleton`, `containers.DeclarativeContainer` trong phần lớn trường hợp.

Framework tự động suy luận dựa trên: Directory Structure, Type Hint, Framework Configuration, Convention.

---

## 5. Mục tiêu cuối cùng

Xime **không** tạo ra HTTP Framework mới, DI Container mới hay ORM mới.

Xime tập trung vào: Convention Engine, Dependency Injection Automation, Dependency Graph Validation, Lifecycle Management, Configuration System, Adapter Integration.

Để các thư viện chuyên biệt xử lý phần việc mà chúng làm tốt nhất.
