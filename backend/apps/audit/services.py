from .models import AuditLog


def record_audit(
    *, actor, action: str, entity: str, entity_id: str | None = None,
    tenant_id: int | None = None, previous_data=None, new_data=None, request=None
) -> AuditLog:
    return AuditLog.objects.create(
        tenant_id=tenant_id,
        user=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        previous_data=previous_data,
        new_data=new_data,
        ip=request.META.get("REMOTE_ADDR") if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000] if request else None,
        request_id=getattr(request, "request_id", None) if request else None,
    )

