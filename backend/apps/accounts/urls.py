from django.urls import path

from .views import (
    ChangePasswordView,
    CustomerBlockView,
    CustomerCloseSessionsView,
    CustomerDetailView,
    CustomerListView,
    CustomerPasswordResetView,
    CustomerRegisterView,
    CustomerUnblockView,
    DeleteAccountView,
    EmailCodeSendView,
    EmailConfirmView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    RefreshView,
    SessionCloseOthersView,
    SessionCloseView,
    SessionListView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path("auth/register/", CustomerRegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),

    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path(
        "auth/password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "auth/password-reset/verify/",
        PasswordResetVerifyView.as_view(),
        name="password-reset-verify",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("usuarios/", UserListCreateView.as_view(), name="user-list-create"),
    path("usuarios/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    # Cuentas de los turistas: SuperAdmin o rol con CLIENTES_GESTIONAR.
    path("admin/clientes/", CustomerListView.as_view(), name="customer-list"),
    path("admin/clientes/<int:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
    path("admin/clientes/<int:pk>/bloquear/", CustomerBlockView.as_view(), name="customer-block"),
    path("admin/clientes/<int:pk>/desbloquear/", CustomerUnblockView.as_view(), name="customer-unblock"),
    path("admin/clientes/<int:pk>/cerrar-sesiones/", CustomerCloseSessionsView.as_view(), name="customer-sessions"),
    path(
        "admin/clientes/<int:pk>/recuperar-contrasena/",
        CustomerPasswordResetView.as_view(),
        name="customer-password-reset",
    ),
    # La cuenta del propio usuario: correo, contrasena, sesiones y baja.
    path("auth/correo/enviar-codigo/", EmailCodeSendView.as_view(), name="email-code-send"),
    path("auth/correo/verificar/", EmailConfirmView.as_view(), name="email-confirm"),
    path("auth/me/contrasena/", ChangePasswordView.as_view(), name="change-password"),
    path("auth/me/sesiones/", SessionListView.as_view(), name="session-list"),
    path("auth/me/sesiones/cerrar-otras/", SessionCloseOthersView.as_view(), name="session-close-others"),
    path("auth/me/sesiones/<int:pk>/cerrar/", SessionCloseView.as_view(), name="session-close"),
    path("auth/me/eliminar/", DeleteAccountView.as_view(), name="delete-account"),
]
