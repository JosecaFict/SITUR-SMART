"""Genera un script SQL equivalente a ``seed_bolivia`` para ejecutarlo en pgAdmin.

Sirve para cargar los datos en una base a la que no se llega con
``manage.py`` (por ejemplo la de Railway desde el Query Tool). Replica lo que
hacen los services del backend: empresa con propietario y suscripcion, roles
propios, empleados, hoteles con ficha y habitaciones, productos y turistas.

El script entero es un solo bloque ``DO``: si algo falla no queda nada a medias.
Una empresa que ya existe (por nombre comercial) se omite, igual que en el
comando, asi que se puede ejecutar mas de una vez.

Las contrasenas viajan ya cifradas con el hasher de Django configurado (Argon2),
nunca en texto plano.
"""

import json

from django.contrib.auth.hashers import make_password
from django.utils.text import slugify

from . import bolivia

TAG = "$seed$"


def q(value) -> str:
    """Literal SQL. None -> NULL; textos con comillas escapadas."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _code_generator():
    """Mismo algoritmo que ``_unique_product_code`` dentro de una empresa nueva."""
    used: set[str] = set()

    def next_code(name: str) -> str:
        base = (slugify(name).replace("-", "_") or "PRODUCTO").upper()[:60]
        candidate, suffix = base, 2
        while candidate in used:
            marker = f"_{suffix}"
            candidate = f"{base[: 60 - len(marker)]}{marker}"
            suffix += 1
        used.add(candidate)
        return candidate

    return next_code


def _city(name: str) -> str:
    return f"(SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = {q(name)})"


def _user(account: dict, password_hash: str) -> list[str]:
    """Busca el usuario por email o lo crea; deja su id en v_user."""
    return [
        f"    SELECT id INTO v_user FROM usuario WHERE email = {q(account['email'])};",
        "    IF v_user IS NULL THEN",
        "      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)",
        f"      VALUES ({q(account['email'])}, {q(password_hash)}, {q(account['nombres'])}, "
        f"{q(account['apellidos'])}, 'ACTIVO') RETURNING id INTO v_user;",
        "    END IF;",
    ]


def _member(role_sql: str) -> list[str]:
    return [
        "    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')",
        "      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';",
        f"    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, {role_sql}, v_tenant);",
    ]


def _product(
    type_code: str, code: str, item: dict, *, city_sql: str, locality, price, capacity, status
) -> str:
    return (
        "    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, "
        "nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)\n"
        f"    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = {q(type_code)}), {city_sql}, "
        f"v_moneda, {q(code)}, {q(item['nombre'])}, {q(item['descripcion'])}, {q(locality)}, "
        f"{price}, {capacity}, {q(status)}) RETURNING id INTO v_producto;"
    )


def _company(empresa: dict) -> list[str]:
    owner, *staff = bolivia.cuentas_empresa(empresa)
    hashed = {c["email"]: make_password(bolivia.PASSWORD) for c in [owner, *staff]}
    initial_status = "PENDIENTE" if empresa["estado"] == "PENDIENTE" else "ACTIVO"
    subdomain = slugify(empresa["nombre"]).lower()[:63].strip("-")
    next_code = _code_generator()

    lines = [
        "",
        f"  -- {empresa['nombre']} ({empresa['perfil']})",
        f"  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = {q(empresa['nombre'])}) THEN",
        f"    v_sub := {q(subdomain)}; v_n := 2;",
        "    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP",
        f"      v_sub := {q(subdomain[:60])} || '-' || v_n; v_n := v_n + 1;",
        "    END LOOP;",
        "    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)",
        f"    VALUES ({_city(empresa['ciudad'])}, {q(empresa['nombre'])}, {q(empresa['nombre'])}, v_sub, "
        f"{q(bolivia.email('contacto', empresa['dominio']))}, {q(initial_status)}) RETURNING id INTO v_tenant;",
        "    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, "
        "precio_contratado, id_moneda_contratada, periodicidad_contratada)",
        "    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad",
        f"      FROM plan p WHERE p.codigo = {q(empresa['plan'])};",
        "    v_user := NULL;",
        *_user(owner, hashed[owner["email"]]),
        *_member("v_rol_admin"),
    ]

    for code in dict.fromkeys(c["rol"] for c in staff):
        if code in bolivia.ROLES_PERSONALIZADOS:
            role = bolivia.ROLES_PERSONALIZADOS[code]
            permissions = ", ".join(q(p) for p in role["permisos"])
            lines += [
                "    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)",
                f"    VALUES (v_tenant, {q(code)}, {q(role['nombre'])}, 'TENANT', FALSE) RETURNING id INTO v_rol;",
                "    INSERT INTO rol_permiso (id_rol, id_permiso)",
                f"    SELECT v_rol, id FROM permiso WHERE codigo IN ({permissions});",
            ]

    for account in staff:
        role_sql = (
            f"(SELECT id FROM rol WHERE codigo = {q(account['rol'])} AND ambito = 'TENANT' "
            "AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1)"
        )
        lines += ["    v_user := NULL;", *_user(account, hashed[account["email"]]), *_member(role_sql)]

    for hotel in empresa["hoteles"]:
        city_sql = _city(hotel["ciudad"])
        lines += [
            _product("HOTEL", next_code(hotel["nombre"]), hotel, city_sql=city_sql,
                     locality=hotel["localidad"], price=0, capacity=1, status=hotel["estado"]),
            "    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, "
            "latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)",
            "    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), "
            f"{q(hotel['direccion'])}, {hotel['latitud']}, {hotel['longitud']}, {hotel['estrellas']}, "
            f"{q(hotel['check_in'].strftime('%H:%M'))}, {q(hotel['check_out'].strftime('%H:%M'))}, "
            f"{q(json.dumps(hotel['servicios'], ensure_ascii=False))}::jsonb) RETURNING id INTO v_hotel;",
        ]
        for room in hotel["habitaciones"]:
            lines += [
                _product("HABITACION", next_code(room["nombre"]), room, city_sql=city_sql,
                         locality=hotel["localidad"], price=room["precio_base"],
                         capacity=room["capacidad_maxima"], status=room["estado"]),
                "    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, "
                "capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)",
                f"    VALUES (v_producto, v_hotel, v_tenant, {room['cantidad_habitaciones']}, "
                f"{room['capacidad_adultos']}, {room['capacidad_ninos']}, {q(room['tipo_cama'])}, "
                f"{q(room['incluye_desayuno'])});",
            ]

    for item in empresa["productos"]:
        lines.append(
            _product(item["tipo"], next_code(item["nombre"]), item, city_sql=_city(item["ciudad"]),
                     locality=item["localidad"], price=item["precio_base"],
                     capacity=item["capacidad_maxima"], status=item["estado"])
        )

    if empresa["estado"] == "SUSPENDIDO":
        lines.append("    UPDATE tenant SET estado = 'SUSPENDIDO' WHERE id = v_tenant;")
    lines += ["    v_empresas := v_empresas + 1;", "  END IF;"]
    return lines


def _tours(empresa: dict) -> list[str]:
    """Fichas, recorridos, guias y salidas de los tours (CU20).

    Va aparte de ``_company`` porque tambien tiene que completar empresas que ya
    existian antes de CU20. Todo es idempotente: la ficha y los guias se crean
    una vez y las salidas repetidas chocan con uq_disponibilidad_producto_inicio
    y se omiten, asi que cada ejecucion solo suma las semanas que falten.
    """
    tours = [item for item in empresa["productos"] if item.get("ficha")]
    if not tours or empresa["estado"] != "ACTIVO":
        return []
    lines = [
        "",
        f"  -- Tours de {empresa['nombre']}",
        f"  v_tenant := NULL; SELECT id INTO v_tenant FROM tenant WHERE nombre_comercial = {q(empresa['nombre'])} "
        "AND estado = 'ACTIVO';",
        "  IF v_tenant IS NOT NULL THEN",
    ]
    for guide in bolivia.guias_empresa(empresa):
        lines += [
            "    INSERT INTO guia (id_tenant, nombres, idiomas)",
            f"    SELECT v_tenant, {q(guide['nombres'])}, {q(json.dumps(guide['idiomas'], ensure_ascii=False))}::jsonb",
            f"    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = {q(guide['nombres'])});",
        ]
    guide_names = {guide["usuario"]: guide["nombres"] for guide in bolivia.guias_empresa(empresa)}
    days = 7 * bolivia.SEMANAS_SALIDAS

    for item in tours:
        ficha = item["ficha"]
        lines += [
            "    v_producto := NULL;",
            "    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto",
            f"     WHERE p.id_tenant = v_tenant AND p.nombre = {q(item['nombre'])} AND t.codigo = {q(item['tipo'])};",
            "    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN",
            "      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, "
            "punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)",
            f"      VALUES (v_producto, v_tenant, {ficha['duracion_minutos']}, {q(ficha['idioma'])}, "
            f"{q(ficha['dificultad'])}, {q(ficha['edad_minima'])}, {q(ficha['punto_encuentro'])}, "
            f"{ficha['latitud']}, {ficha['longitud']}, "
            f"{q(json.dumps(ficha['incluye'], ensure_ascii=False))}::jsonb, "
            f"{q(json.dumps(ficha['no_incluye'], ensure_ascii=False))}::jsonb, {q(ficha['requisitos'])});",
        ]
        for order, stop in enumerate(ficha["paradas"], start=1):
            lines.append(
                "      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) "
                f"VALUES (v_producto, v_tenant, {order}, {q(stop['nombre'])}, {q(stop['descripcion'])}, "
                f"{q(stop['duracion_minutos'])});"
            )
        lines += [
            # Desde ahora se vende por salidas: los cupos diarios futuros dejan de venderse.
            "      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto "
            "AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;",
            "    END IF;",
        ]
        schedule = ficha["salidas"]
        if schedule["horas"]:
            iso_days = ", ".join(str(day + 1) for day in schedule["dias"])
            guide_sql = (
                f"(SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = {q(guide_names[schedule['guia']])})"
                if schedule["guia"] else "NULL"
            )
            for hour in schedule["horas"]:
                start = f"((g.d + TIME {q(hour)}) AT TIME ZONE 'America/La_Paz')"
                lines += [
                    "    IF v_producto IS NOT NULL THEN",
                    "      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)",
                    f"      SELECT v_producto, v_tenant, {start}, {start} + INTERVAL '{ficha['duracion_minutos']} minutes', "
                    f"p.capacidad_maxima, {guide_sql}",
                    "        FROM producto_turistico p,",
                    f"             generate_series(CURRENT_DATE + 1, CURRENT_DATE + {days}, INTERVAL '1 day') AS g(d)",
                    f"       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN ({iso_days})",
                    "      ON CONFLICT (id_producto, inicio) DO NOTHING;",
                    "    END IF;",
                ]
    lines.append("  END IF;")
    return lines


def render(*, limpiar_demo_viejo: bool = False) -> str:
    lines = [
        "-- ============================================================",
        "-- SITUR-SMART: datos de demostracion de Bolivia",
        "-- Generado con: python manage.py seed_bolivia --sql",
        "-- No editar a mano: los datos viven en backend/apps/catalog/seed/bolivia.py",
        "--",
        f"-- Contrasena de todas las cuentas: {bolivia.PASSWORD} (aqui viaja cifrada).",
        "-- Se puede ejecutar mas de una vez: las empresas que ya existen se omiten y a los",
        "-- tours solo se les suman las salidas de las semanas que falten.",
        "-- Si algo falla, no se guarda nada.",
        "-- ============================================================",
        "",
        f"DO {TAG}",
        "DECLARE",
        "  v_pais BIGINT; v_moneda BIGINT; v_rol_admin BIGINT; v_rol_cliente BIGINT;",
        "  v_tenant BIGINT; v_user BIGINT; v_rol BIGINT; v_producto BIGINT; v_hotel BIGINT;",
        "  v_sub TEXT; v_n INT; v_empresas INT := 0; v_turistas INT := 0;",
        "BEGIN",
        f"  SELECT id INTO STRICT v_pais FROM pais WHERE codigo_iso = {q(bolivia.PAIS)};",
        f"  SELECT id INTO STRICT v_moneda FROM moneda WHERE codigo_iso = {q(bolivia.MONEDA)};",
        "  SELECT id INTO STRICT v_rol_admin FROM rol WHERE codigo = 'TENANT_ADMIN' AND ambito = 'TENANT' "
        "AND id_tenant IS NULL;",
        "  SELECT id INTO STRICT v_rol_cliente FROM rol WHERE codigo = 'CLIENTE' AND ambito = 'GLOBAL';",
        "",
        "  -- Ciudades que faltan en la siembra inicial",
    ]
    for city in bolivia.CIUDADES_NUEVAS:
        lines.append(
            "  INSERT INTO ciudad (id_pais, nombre, latitud, longitud, zona_horaria) "
            f"VALUES (v_pais, {q(city['nombre'])}, {city['latitud']}, {city['longitud']}, 'America/La_Paz') "
            "ON CONFLICT (id_pais, nombre) DO NOTHING;"
        )

    if limpiar_demo_viejo:
        names = ", ".join(q(n) for n in bolivia.DEMO_VIEJO_EMPRESAS)
        emails = ", ".join(q(e) for e in bolivia.DEMO_VIEJO_EMAILS)
        lines += [
            "",
            "  -- Desactiva las empresas ficticias del seed anterior (no las borra)",
            f"  UPDATE tenant SET estado = 'INACTIVO' WHERE nombre_comercial IN ({names}) AND estado <> 'INACTIVO';",
            f"  UPDATE usuario SET estado = 'INACTIVO' WHERE email IN ({emails}) AND estado <> 'INACTIVO';",
        ]

    for empresa in bolivia.EMPRESAS:
        lines += _company(empresa)

    lines += ["", "  -- Tours y experiencias (CU20): fichas, guias y salidas de las proximas semanas"]
    for empresa in bolivia.EMPRESAS:
        lines += _tours(empresa)

    lines += ["", "  -- Turistas"]
    for tourist in bolivia.cuentas_turistas():
        lines += [
            f"  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = {q(tourist['email'])}) THEN",
            "    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)",
            f"    VALUES ({q(tourist['email'])}, {q(make_password(bolivia.PASSWORD))}, {q(tourist['nombres'])}, "
            f"{q(tourist['apellidos'])}, 'ACTIVO') RETURNING id INTO v_user;",
            "    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);",
            "    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);",
            "    v_turistas := v_turistas + 1;",
            "  END IF;",
        ]

    lines += [
        "",
        "  INSERT INTO bitacora (accion, entidad, datos_nuevos)",
        "  VALUES ('SEED_DEMO', 'seed_bolivia', jsonb_build_object('empresas', v_empresas, 'turistas', v_turistas));",
        "  RAISE NOTICE 'SITUR-SMART: % empresas y % turistas creados', v_empresas, v_turistas;",
        "END",
        f"{TAG};",
        "",
    ]
    return "\n".join(lines)
