from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.schemas.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordVerifyCode,
    RefreshRequest,
    UserCreate,
    VerificationRequest,
)


class TestAuthRoutes:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = str(uuid4())
        user.fullname = "Test User"
        user.email = "test@example.com"
        user.phone = "+1234567890"
        user.is_active = True
        user.is_admin = False
        user.is_verified = True
        user.hashed_password = "hashed_password"
        user.notif_setting = True
        user.created_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        return user

    @pytest.fixture
    def mock_verification_code(self):
        code = MagicMock()
        code.id = str(uuid4())
        code.user_id = str(uuid4())
        code.code = "123456"
        code.type = "email"
        code.expires_at = datetime.utcnow() + timedelta(hours=1)
        code.is_used = False
        code.created_at = datetime.utcnow()
        return code

    @pytest.mark.asyncio
    async def test_register_with_email_success(self, mock_db):
        user_data = UserCreate(fullname="Test User", email="test@example.com", phone="", password="password123")

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with (
            patch("app.api.routes.v1.auth.get_password_hash", return_value="hashed_password"),
            patch("app.api.routes.v1.auth.create_verification_code") as mock_create_code,
            patch("app.api.routes.v1.auth.send_verification_code") as mock_send_code,
            patch(
                "app.api.routes.v1.auth.uuid4",
                side_effect=[
                    UUID("12345678-1234-5678-9012-123456789012"),
                    UUID("87654321-4321-8765-2109-876543210987"),
                ],
            ),
        ):
            mock_verification = MagicMock()
            mock_verification.code = "123456"
            mock_create_code.return_value = mock_verification

            from app.api.routes.v1.auth import register

            result = await register(user_in=user_data, db=mock_db)

            assert result["fullname"] == "Test User"
            assert result["email"] == "test@example.com"
            assert result["phone"] is None
            assert result["is_active"] is True
            assert result["is_verified"] is False
            mock_create_code.assert_called_once()
            mock_send_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_with_phone_success(self, mock_db):
        user_data = UserCreate(fullname="Test User", email=None, phone="+1234567890", password="password123")

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with (
            patch("app.api.routes.v1.auth.get_password_hash", return_value="hashed_password"),
            patch("app.api.routes.v1.auth.create_verification_code") as mock_create_code,
            patch(
                "app.api.routes.v1.auth.uuid4",
                side_effect=[
                    UUID("12345678-1234-5678-9012-123456789012"),
                    UUID("87654321-4321-8765-2109-876543210987"),
                ],
            ),
        ):
            mock_verification = MagicMock()
            mock_verification.code = "123456"
            mock_create_code.return_value = mock_verification

            from app.api.routes.v1.auth import register

            result = await register(user_in=user_data, db=mock_db)

            assert result["fullname"] == "Test User"
            assert result["phone"] == "+1234567890"
            mock_create_code.assert_called_once_with(mock_db, "12345678-1234-5678-9012-123456789012", "phone")

    @pytest.mark.asyncio
    async def test_login_success(self, mock_db, mock_user):
        form_data = MagicMock()
        form_data.username = "test@example.com"
        form_data.password = "password123"

        with (
            patch("app.api.routes.v1.auth.authenticate_user", return_value=mock_user),
            patch("app.api.routes.v1.auth.create_access_token", return_value="access_token"),
            patch("app.api.routes.v1.auth.create_refresh_token", return_value="refresh_token"),
            patch("app.api.routes.v1.auth.settings") as mock_settings,
        ):
            mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30

            from app.api.routes.v1.auth import login

            result = await login(form_data=form_data, db=mock_db)

            assert result["access_token"] == "access_token"
            assert result["token_type"] == "bearer"
            assert result["refresh_token"] == "refresh_token"

    @pytest.mark.asyncio
    async def test_login_incorrect_credentials(self, mock_db):
        form_data = MagicMock()
        form_data.username = "test@example.com"
        form_data.password = "wrong_password"

        with patch("app.api.routes.v1.auth.authenticate_user", return_value=None):
            from app.api.routes.v1.auth import login

            with pytest.raises(HTTPException) as exc_info:
                await login(form_data=form_data, db=mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Incorrect username or password" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, mock_db, mock_user):
        mock_user.is_active = False
        form_data = MagicMock()
        form_data.username = "test@example.com"
        form_data.password = "password123"

        with patch("app.api.routes.v1.auth.authenticate_user", return_value=mock_user):
            from app.api.routes.v1.auth import login

            with pytest.raises(HTTPException) as exc_info:
                await login(form_data=form_data, db=mock_db)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Inactive user" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        refresh_data = RefreshRequest(refresh_token="valid_refresh_token")

        mock_payload = {"sub": "user_id", "type": "refresh"}

        with (
            patch("app.api.routes.v1.auth.jwt.decode", return_value=mock_payload),
            patch("app.api.routes.v1.auth.create_access_token", return_value="new_access_token"),
            patch("app.api.routes.v1.auth.settings") as mock_settings,
        ):
            mock_settings.SECRET_KEY = "secret"
            mock_settings.ALGORITHM = "HS256"

            from app.api.routes.v1.auth import refresh_token

            result = await refresh_token(data=refresh_data)

            assert result["access_token"] == "new_access_token"
            assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_type(self):
        refresh_data = RefreshRequest(refresh_token="invalid_token")

        mock_payload = {"sub": "user_id", "type": "access"}  # Wrong type

        with (
            patch("app.api.routes.v1.auth.jwt.decode", return_value=mock_payload),
            patch("app.api.routes.v1.auth.settings") as mock_settings,
        ):
            mock_settings.SECRET_KEY = "secret"
            mock_settings.ALGORITHM = "HS256"

            from app.api.routes.v1.auth import refresh_token

            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(data=refresh_data)

            assert exc_info.value.status_code == 401
            assert "Invalid token type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_refresh_token_jwt_error(self):
        refresh_data = RefreshRequest(refresh_token="invalid_token")

        with (
            patch("app.api.routes.v1.auth.jwt.decode", side_effect=jwt.JWTError()),
            patch("app.api.routes.v1.auth.settings") as mock_settings,
        ):
            mock_settings.SECRET_KEY = "secret"
            mock_settings.ALGORITHM = "HS256"

            from app.api.routes.v1.auth import refresh_token

            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(data=refresh_data)

            assert exc_info.value.status_code == 401
            assert "Invalid or expired refresh token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_me_success(self, mock_user):
        from app.api.routes.v1.auth import get_me

        result = await get_me(current_user=mock_user)

        assert result["id"] == mock_user.id
        assert result["email"] == mock_user.email
        assert result["is_active"] == mock_user.is_active

    @pytest.mark.asyncio
    async def test_get_notif_setting_success(self, mock_user):
        from app.api.routes.v1.auth import get_notif_setting

        result = await get_notif_setting(current_user=mock_user)

        assert result["notif_setting"] == mock_user.notif_setting

    @pytest.mark.asyncio
    async def test_verify_user_email_success(self, mock_db, mock_user, mock_verification_code):
        verification_data = VerificationRequest(code="123456")
        mock_user.email = "test@example.com"
        mock_user.is_verified = False

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_verification_code
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.auth import verify_user

        result = await verify_user(
            verification_type="email", verification_data=verification_data, db=mock_db, current_user=mock_user
        )

        assert result["message"] == "User verified via email"
        assert result["is_verified"] is True
        assert mock_verification_code.is_used is True
        assert mock_user.is_verified is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_user_invalid_type(self, mock_db, mock_user):
        verification_data = VerificationRequest(code="123456")

        from app.api.routes.v1.auth import verify_user

        with pytest.raises(HTTPException) as exc_info:
            await verify_user(
                verification_type="invalid", verification_data=verification_data, db=mock_db, current_user=mock_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid verification type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_user_no_email(self, mock_db, mock_user):
        verification_data = VerificationRequest(code="123456")
        mock_user.email = None

        from app.api.routes.v1.auth import verify_user

        with pytest.raises(HTTPException) as exc_info:
            await verify_user(
                verification_type="email", verification_data=verification_data, db=mock_db, current_user=mock_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "User does not have an email" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_user_no_phone(self, mock_db, mock_user):
        verification_data = VerificationRequest(code="123456")
        mock_user.phone = None

        from app.api.routes.v1.auth import verify_user

        with pytest.raises(HTTPException) as exc_info:
            await verify_user(
                verification_type="phone", verification_data=verification_data, db=mock_db, current_user=mock_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "User does not have a phone" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_user_no_valid_code(self, mock_db, mock_user):
        verification_data = VerificationRequest(code="123456")
        mock_user.email = "test@example.com"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.auth import verify_user

        with pytest.raises(HTTPException) as exc_info:
            await verify_user(
                verification_type="email", verification_data=verification_data, db=mock_db, current_user=mock_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "No valid verification code found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_user_wrong_code(self, mock_db, mock_user, mock_verification_code):
        verification_data = VerificationRequest(code="wrong_code")
        mock_user.email = "test@example.com"
        mock_verification_code.code = "123456"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_verification_code
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.auth import verify_user

        with pytest.raises(HTTPException) as exc_info:
            await verify_user(
                verification_type="email", verification_data=verification_data, db=mock_db, current_user=mock_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid verification code" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_resend_verification_success(self, mock_db, mock_user):
        mock_user.email = "test@example.com"
        mock_user.is_verified = False

        with (
            patch("app.api.routes.v1.auth.create_verification_code") as mock_create_code,
            patch("app.api.routes.v1.auth.send_verification_code") as mock_send_code,
        ):
            mock_verification = MagicMock()
            mock_verification.code = "123456"
            mock_create_code.return_value = mock_verification

            from app.api.routes.v1.auth import resend_verification

            result = await resend_verification(verification_type="email", db=mock_db, current_user=mock_user)

            assert result["message"] == "Verification code sent via email"
            mock_create_code.assert_called_once_with(mock_db, mock_user.id, "email")
            mock_send_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_resend_verification_already_verified(self, mock_db, mock_user):
        mock_user.is_verified = True

        from app.api.routes.v1.auth import resend_verification

        with pytest.raises(HTTPException) as exc_info:
            await resend_verification(verification_type="email", db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "User is already verified" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_db, mock_user):
        mock_user.is_verified = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.auth import get_user

        result = await get_user(username="test@example.com", db=mock_db, current_user=mock_user)

        assert result["id"] == mock_user.id
        assert result["email"] == mock_user.email
        assert result["is_verified"] == mock_user.is_verified

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_db, mock_user):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.auth import get_user

        result = await get_user(username="nonexistent@example.com", db=mock_db, current_user=mock_user)

        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_user_not_verified(self, mock_db, mock_user):
        found_user = MagicMock()
        found_user.is_verified = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = found_user
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.auth import get_user

        result = await get_user(username="test@example.com", db=mock_db, current_user=mock_user)

        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_send_password_reset_code_success(self, mock_db, mock_user):
        request_data = ForgotPasswordRequest(email="test@example.com")
        mock_request = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with (
            patch("app.api.routes.v1.auth.check_rate_limit") as mock_rate_limit,
            patch("app.api.routes.v1.auth.create_verification_code") as mock_create_code,
            patch("app.api.routes.v1.auth.send_verification_code") as mock_send_code,
        ):
            mock_verification = MagicMock()
            mock_verification.code = "123456"
            mock_create_code.return_value = mock_verification

            from app.api.routes.v1.auth import send_password_reset_code

            result = await send_password_reset_code(request_data=request_data, request=mock_request, db=mock_db)

            assert result.success is True
            assert "Password reset code sent" in result.message
            mock_rate_limit.assert_called_once()
            mock_create_code.assert_called_once()
            mock_send_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_password_reset_code_user_not_found(self, mock_db):
        request_data = ForgotPasswordRequest(email="nonexistent@example.com")
        mock_request = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.auth.check_rate_limit"):
            from app.api.routes.v1.auth import send_password_reset_code

            result = await send_password_reset_code(request_data=request_data, request=mock_request, db=mock_db)

            assert result.success is True
            assert "If this email exists" in result.message

    @pytest.mark.asyncio
    async def test_send_password_reset_code_inactive_user(self, mock_db, mock_user):
        request_data = ForgotPasswordRequest(email="test@example.com")
        mock_request = MagicMock()
        mock_user.is_active = False

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.auth.check_rate_limit"):
            from app.api.routes.v1.auth import send_password_reset_code

            with pytest.raises(HTTPException) as exc_info:
                await send_password_reset_code(request_data=request_data, request=mock_request, db=mock_db)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Account is deactivated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_password_reset_code_success(self, mock_db, mock_user, mock_verification_code):
        verify_data = ForgotPasswordVerifyCode(email="test@example.com", verify_code="123456")
        mock_request = MagicMock()

        mock_results = [MagicMock(), MagicMock()]  # User query  # Verification code query
        mock_results[0].scalars.return_value.first.return_value = mock_user
        mock_results[1].scalars.return_value.first.return_value = mock_verification_code
        mock_db.execute.side_effect = mock_results

        with (
            patch("app.api.routes.v1.auth.check_rate_limit"),
            patch("app.api.routes.v1.auth.jwt.encode", return_value="reset_token"),
        ):
            from app.api.routes.v1.auth import verify_password_reset_code

            result = await verify_password_reset_code(verify_data=verify_data, request=mock_request, db=mock_db)

            assert result.success is True
            assert "Verification code is valid" in result.message
            assert result.token == "reset_token"
