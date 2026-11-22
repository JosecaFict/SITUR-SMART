from django.db import migrations


def seed_permission(apps, schema_editor):
    # Legacy models are unmanaged; pure SQLite test migrations do not create their tables.
    if "permiso" not in schema_editor.connection.introspection.table_names():
        return
    Permission = apps.get_model("rbac", "Permission")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    alias = schema_editor.connection.alias
    permission, _ = Permission.objects.using(alias).get_or_create(
        code="COMUNICACIONES_GESTIONAR",
        defaults={"module": "Comunicaciones", "name": "Gestionar comunicaciones y avisos"},
    )
    for role in Role.objects.using(alias).filter(code__in=("TENANT_ADMIN", "SUPER_ADMIN"), is_system=True):
        RolePermission.objects.using(alias).get_or_create(role_id=role.id, permission_id=permission.id)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_communication_communicationdelivery_pushattempt_and_more"),
        ("rbac", "0001_initial"),
    ]
    operations = [migrations.RunPython(seed_permission, migrations.RunPython.noop)]
