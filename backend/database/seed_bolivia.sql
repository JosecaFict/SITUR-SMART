-- ============================================================
-- SITUR-SMART: datos de demostracion de Bolivia
-- Generado con: python manage.py seed_bolivia --sql
-- No editar a mano: los datos viven en backend/apps/catalog/seed/bolivia.py
--
-- Contrasena de todas las cuentas: Admin123* (aqui viaja cifrada).
-- Se puede ejecutar mas de una vez: las empresas que ya existen se omiten.
-- Si algo falla, no se guarda nada.
-- ============================================================

DO $seed$
DECLARE
  v_pais BIGINT; v_moneda BIGINT; v_rol_admin BIGINT; v_rol_cliente BIGINT;
  v_tenant BIGINT; v_user BIGINT; v_rol BIGINT; v_producto BIGINT; v_hotel BIGINT;
  v_sub TEXT; v_n INT; v_empresas INT := 0; v_turistas INT := 0;
BEGIN
  SELECT id INTO STRICT v_pais FROM pais WHERE codigo_iso = 'BOL';
  SELECT id INTO STRICT v_moneda FROM moneda WHERE codigo_iso = 'BOB';
  SELECT id INTO STRICT v_rol_admin FROM rol WHERE codigo = 'TENANT_ADMIN' AND ambito = 'TENANT' AND id_tenant IS NULL;
  SELECT id INTO STRICT v_rol_cliente FROM rol WHERE codigo = 'CLIENTE' AND ambito = 'GLOBAL';

  -- Ciudades que faltan en la siembra inicial
  INSERT INTO ciudad (id_pais, nombre, latitud, longitud, zona_horaria) VALUES (v_pais, 'Tarija', -21.535500, -64.729600, 'America/La_Paz') ON CONFLICT (id_pais, nombre) DO NOTHING;
  INSERT INTO ciudad (id_pais, nombre, latitud, longitud, zona_horaria) VALUES (v_pais, 'Tupiza', -21.442800, -65.718900, 'America/La_Paz') ON CONFLICT (id_pais, nombre) DO NOTHING;

  -- Desactiva las empresas ficticias del seed anterior (no las borra)
  UPDATE tenant SET estado = 'INACTIVO' WHERE nombre_comercial IN ('Andes Boutique Hotels', 'Cruceña Hospitality', 'Kanata Turismo', 'Sabores de Bolivia') AND estado <> 'INACTIVO';
  UPDATE usuario SET estado = 'INACTIVO' WHERE email IN ('duenio1@situr.smart', 'duenio2@situr.smart', 'duenio3@situr.smart', 'duenio4@situr.smart') AND estado <> 'INACTIVO';

  -- Hotel Cortez (Solo hotel)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Hotel Cortez') THEN
    v_sub := 'hotel-cortez'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'hotel-cortez' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), 'Hotel Cortez', 'Hotel Cortez', v_sub, 'contacto@hotelcortez.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@hotelcortez.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@hotelcortez.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$N01HZHpTOEp4VkduMXNPemluVktDVw$iW46ldGYlhPQq0CmZofQPj3QkFTrgOHVmuR0l0Q96z0', 'Jefe Admin', 'Hotel Cortez', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'RECEPCIONISTA', 'Recepcionista', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@hotelcortez.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@hotelcortez.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TFBQY3dXdUVqYUFSdXRaRVdGTWhURg$ZD2MYGsKNkJgtoJK9Htc+isNUtcKdegNiXuJd2TUdmU', 'Empleado 1', 'Hotel Cortez', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@hotelcortez.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@hotelcortez.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$S1lkMkY0NXRmWGZORHpTVXhqaGUzVg$uYSk0Te9u1amb/YFBICaTkqJM8N4mOcs9cLhfl+CCKY', 'Empleado 2', 'Hotel Cortez', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'HOTEL_CORTEZ', 'Hotel Cortez', 'Hotel tradicional de Santa Cruz de la Sierra sobre el segundo anillo, a pocos minutos del centro histórico y de la zona de Equipetrol. Piscina rodeada de jardines tropicales, ideal para el clima cálido del oriente.', 'Segundo anillo', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Av. Cristóbal de Mendoza 280, segundo anillo', -17.771300, -63.187300, 4, '14:00', '12:00', '["Wi-Fi", "Piscina", "Desayuno incluido", "Estacionamiento", "Aire acondicionado", "Restaurante", "Recepción 24 h"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'HABITACION_SIMPLE', 'Habitación Simple', 'Habitación para una persona con escritorio y aire acondicionado.', 'Segundo anillo', 350.00, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 12, 1, 0, '1 cama de plaza y media', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'HABITACION_DOBLE_ESTANDAR', 'Habitación Doble Estándar', 'Dos camas individuales, ideal para viajes de trabajo o amigos.', 'Segundo anillo', 480.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 20, 2, 0, '2 camas individuales', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'HABITACION_MATRIMONIAL_SUPERIOR', 'Habitación Matrimonial Superior', 'Cama king, vista a los jardines y la piscina.', 'Segundo anillo', 560.00, 3, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 15, 2, 1, '1 cama king', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'SUITE_CORTEZ', 'Suite Cortez', 'Suite con sala de estar independiente y minibar.', 'Segundo anillo', 850.00, 4, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 4, 2, 2, '1 cama king y sofá cama', TRUE);
    v_empresas := v_empresas + 1;
  END IF;

  -- Hotel La Cúpula (Solo hotel)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Hotel La Cúpula') THEN
    v_sub := 'hotel-la-cupula'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'hotel-la-cupula' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), 'Hotel La Cúpula', 'Hotel La Cúpula', v_sub, 'contacto@hotelcupula.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@hotelcupula.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@hotelcupula.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$SVgxWjNMSk12dXpFbkJCbVI4dFQ4SA$d/VtxTpGlWN3sKlRB9bZ8veQSF5nb+jaXkmQZ4DDTuo', 'Jefe Admin', 'Hotel La Cúpula', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'RECEPCIONISTA', 'Recepcionista', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@hotelcupula.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@hotelcupula.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dlBRWFlvc2JTNUhCa0w0OWpseGhuSg$k8WuCcCOOudtxl+8wly8aoIyAUQbdthmWuhxV10pNr8', 'Empleado 1', 'Hotel La Cúpula', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'HOTEL_LA_CUPULA', 'Hotel La Cúpula', 'Hotel de estilo mediterráneo en la ladera del cerro Calvario, con jardines en terrazas y una de las mejores vistas al Lago Titicaca. Punto de partida para visitar la Isla del Sol.', 'Cerro Calvario', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Calle Michel Pérez 1-3', -16.164700, -69.092000, 2, '13:00', '11:00', '["Wi-Fi", "Restaurante", "Calefacción", "Admite mascotas"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'HABITACION_SIMPLE', 'Habitación Simple', 'Habitación sencilla con baño privado.', 'Cerro Calvario', 180.00, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 4, 1, 0, '1 cama individual', FALSE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'HABITACION_DOBLE', 'Habitación Doble', 'Habitación con vista parcial al lago.', 'Cerro Calvario', 260.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 8, 2, 0, '1 cama matrimonial', FALSE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'SUITE_CON_VISTA_AL_LAGO', 'Suite con Vista al Lago', 'Suite con cocina pequeña y ventanal al Titicaca.', 'Cerro Calvario', 380.00, 3, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 3, 2, 1, '1 cama queen y 1 individual', TRUE);
    v_empresas := v_empresas + 1;
  END IF;

  -- Hoteles Rosario (Cadena: dos hoteles y restaurante)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Hoteles Rosario') THEN
    v_sub := 'hoteles-rosario'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'hoteles-rosario' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), 'Hoteles Rosario', 'Hoteles Rosario', v_sub, 'contacto@hotelesrosario.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'PROFESIONAL';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@hotelesrosario.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$eGkzcjdJVjBHaWtLOGhFZnBuVEVoSA$VuYHNgTNVdXzl4+d48kOrf8B8q/4UClvqsUGUeyapBQ', 'Jefe Admin', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'RECEPCIONISTA', 'Recepcionista', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@hotelesrosario.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$aUpXV3RoT2JhMU9DcmY3c05ha3VnaA$JFjaKU575r13OguIJ6BFSazXbXFA/Ymrq3FqFvFcpws', 'Empleado 1', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@hotelesrosario.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$REtRWllNRFBpeldBWkJqSVNPMHVpZQ$HVK+6Ofz5N9LcZhC8m2jkls6TiHyN2CG/4RjsW2RUpw', 'Empleado 2', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado3@hotelesrosario.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado3@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$VklNVVBQM2VWZzlWQmZrdFFRZkRmZw$4HfVLaUmtmHQKoeE+Ch//1p/f7Hors5Ob9p/eALmbuU', 'Empleado 3', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'HOTEL_ROSARIO_LA_PAZ', 'Hotel Rosario La Paz', 'Hotel de estilo colonial a pasos de la calle Sagárnaga y el Mercado de las Brujas. Patio interior, decoración andina y fácil acceso al casco antiguo.', 'Centro - Calle Illampu', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Av. Illampu 704', -16.496000, -68.141500, 3, '14:00', '11:00', '["Wi-Fi", "Desayuno incluido", "Restaurante", "Calefacción", "Recepción 24 h", "Lavandería"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'HABITACION_SIMPLE', 'Habitación Simple', 'Habitación individual con calefacción.', 'Centro - Calle Illampu', 420.00, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 10, 1, 0, '1 cama individual', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'HABITACION_DOBLE', 'Habitación Doble', 'Habitación doble con vista al patio colonial.', 'Centro - Calle Illampu', 560.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 18, 2, 0, '1 cama matrimonial', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'HABITACION_TRIPLE', 'Habitación Triple', 'Para familias o grupos pequeños.', 'Centro - Calle Illampu', 690.00, 3, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 6, 3, 2, '3 camas individuales', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'SUITE_ROSARIO', 'Suite Rosario', 'Suite amplia con sala y bañera.', 'Centro - Calle Illampu', 790.00, 2, 'BORRADOR') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 2, 2, 0, '1 cama king', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'HOTEL_ROSARIO_DEL_LAGO', 'Hotel Rosario del Lago', 'Hotel frente al Lago Titicaca, a pocas cuadras de la Basílica de Copacabana. Terraza con vista al lago y excursiones a la Isla del Sol.', 'Costanera', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Calle Rigoberto Paredes y Av. Costanera', -16.167600, -69.091500, 3, '14:00', '11:00', '["Wi-Fi", "Desayuno incluido", "Restaurante", "Calefacción", "Estacionamiento"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'HABITACION_DOBLE_VISTA_AL_LAGO', 'Habitación Doble Vista al Lago', 'Ventanal frente al Titicaca.', 'Costanera', 600.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 14, 2, 0, '2 camas individuales', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'HABITACION_MATRIMONIAL', 'Habitación Matrimonial', 'Cama queen y vista al lago.', 'Costanera', 640.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 10, 2, 0, '1 cama queen', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Copacabana'), v_moneda, 'HABITACION_FAMILIAR', 'Habitación Familiar', 'Dos ambientes para familias.', 'Costanera', 820.00, 4, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 4, 3, 2, '1 cama queen y 2 individuales', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'RESTAURANTE_DEL_HOTEL_ROSARIO_LA_PAZ', 'Restaurante del Hotel Rosario La Paz', 'Cocina boliviana y del altiplano: trucha del lago, sopa de quinua y platos con charque. Abierto también para quienes no se hospedan.', 'Centro - Calle Illampu', 85.00, 70, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Hotel Palacio de Sal (Hotel con restaurante)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Hotel Palacio de Sal') THEN
    v_sub := 'hotel-palacio-de-sal'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'hotel-palacio-de-sal' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), 'Hotel Palacio de Sal', 'Hotel Palacio de Sal', v_sub, 'contacto@palaciodesal.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@palaciodesal.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@palaciodesal.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Y1hvTVE2UkJNYTFoWXVnVlM0b1NNSg$vSaG9rJhh1BHEcXx51vKbfrYoFaOD7p6D9mwXkUXAdI', 'Jefe Admin', 'Hotel Palacio de Sal', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'RECEPCIONISTA', 'Recepcionista', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@palaciodesal.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@palaciodesal.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RDk3eGk3dXB4OUM5eGhnbWFqQWlYZw$1NYVvXPuOTanU3dL/L6K/kwEkofbktERVdkdd5pqM1w', 'Empleado 1', 'Hotel Palacio de Sal', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@palaciodesal.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@palaciodesal.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$OWZ2VHJiSkVYZ2NGSGcxTWV5Q0RFNw$deaYaNdnFPVzWv0kQIVxRS5efY9GsA6GdxI9nduz6H8', 'Empleado 2', 'Hotel Palacio de Sal', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'HOTEL_PALACIO_DE_SAL', 'Hotel Palacio de Sal', 'Hotel construido con bloques de sal a orillas del Salar de Uyuni, cerca de Colchani. Muros, muebles y esculturas de sal, con spa y piscina temperada para las noches frías del altiplano.', 'Orillas del Salar - Colchani', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Borde del Salar de Uyuni, zona Colchani', -20.332600, -66.932700, 4, '13:00', '10:00', '["Wi-Fi", "Desayuno incluido", "Restaurante", "Spa", "Piscina", "Calefacción", "Estacionamiento", "Bar"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'HABITACION_DOBLE', 'Habitación Doble', 'Habitación con muros de sal y calefacción.', 'Orillas del Salar - Colchani', 1100.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 12, 2, 0, '2 camas individuales', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'HABITACION_MATRIMONIAL', 'Habitación Matrimonial', 'Cama queen con cabecera de sal tallada.', 'Orillas del Salar - Colchani', 1150.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 10, 2, 0, '1 cama queen', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'SUITE_SALAR', 'Suite Salar', 'Suite con vista directa al salar.', 'Orillas del Salar - Colchani', 1600.00, 3, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 3, 2, 1, '1 cama king', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'RESTAURANTE_DEL_PALACIO_DE_SAL', 'Restaurante del Palacio de Sal', 'Cocina andina de autor con carne de llama, quinua real y vinos tarijeños.', 'Orillas del Salar - Colchani', 120.00, 60, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Parador Santa María La Real (Hotel con restaurante)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Parador Santa María La Real') THEN
    v_sub := 'parador-santa-maria-la-real'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'parador-santa-maria-la-real' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), 'Parador Santa María La Real', 'Parador Santa María La Real', v_sub, 'contacto@paradorsantamaria.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@paradorsantamaria.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@paradorsantamaria.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$WWFoUVVhcXh4eVJXSGY3T0JzanpJNA$/0t4rH7fv2lKRXwaLFZRWyJVS1kzPhBQH0tMo2CIMvc', 'Jefe Admin', 'Parador Santa María La Real', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'RECEPCIONISTA', 'Recepcionista', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@paradorsantamaria.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@paradorsantamaria.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$MWNvZmk2TUF4U0lhRDFnZzVxTnU0NA$S3jZ2q2/yNBQ9AlOkpKHbB3ErRIJ/lQpxBuS7MbwwJg', 'Empleado 1', 'Parador Santa María La Real', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), v_moneda, 'PARADOR_SANTA_MARIA_LA_REAL', 'Parador Santa María La Real', 'Casona colonial del siglo XVIII restaurada en el centro histórico de Sucre, Patrimonio de la Humanidad. Patios, túneles históricos y terraza con vista a los techos blancos de la ciudad.', 'Centro Histórico', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Calle Bolívar 625', -19.047600, -65.259000, 4, '14:00', '12:00', '["Wi-Fi", "Desayuno incluido", "Restaurante", "Spa", "Recepción 24 h", "Bar"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), v_moneda, 'HABITACION_SUPERIOR', 'Habitación Superior', 'Mobiliario colonial y techos altos.', 'Centro Histórico', 650.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 10, 2, 0, '1 cama queen', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), v_moneda, 'HABITACION_DELUXE', 'Habitación Deluxe', 'Balcón hacia el patio principal.', 'Centro Histórico', 780.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 8, 2, 0, '1 cama king', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), v_moneda, 'SUITE_COLONIAL', 'Suite Colonial', 'Suite con sala y bañera de época.', 'Centro Histórico', 980.00, 3, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 3, 2, 1, '1 cama king y sofá cama', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), v_moneda, 'RESTAURANTE_DEL_PARADOR', 'Restaurante del Parador', 'Cocina chuquisaqueña en el patio colonial: chorizos chuquisaqueños, mondongo y chocolates de Sucre.', 'Centro Histórico', 95.00, 50, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- SczTourBo (Agencia completa (hotel en convenio, tours y paquetes))
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'SczTourBo') THEN
    v_sub := 'scztourbo'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'scztourbo' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), 'SczTourBo', 'SczTourBo', v_sub, 'contacto@scztourbo.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'EMPRESARIAL';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$aHZMdllmZG9HcU10SjJ3SjNlU0FMbw$/F9iliEWvrDb8sIMzQWagc1PSbRnE+EL9USqjbhoADA', 'Jefe Admin', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'ENCARGADO_CATALOGO', 'Encargado de catálogo', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'PRODUCTOS_GESTIONAR', 'DISPONIBILIDAD_GESTIONAR', 'REPORTES_TENANT');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dHZlTGhUVDZLMTRJTlc1OHZPaUUwbw$bOacaqjegajEoWptNdf1j7Z0TEyInERZ+g15AZGvApY', 'Empleado 1', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'ENCARGADO_CATALOGO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$WXdLendNWWhEVUxCcnRvTEg3d3pCdQ$zoqngWA4bcq0K4Df/952u+AAjuylNh7Y6O6Tg/gvKdE', 'Empleado 2', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$c1picHJvZ0lCZVFrTEtBM0ZQTFJ0ag$toHOnTmDzqFg7j6o4UwrivmZziEqimoflUotUxDf9v0', 'Guía 1', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$aTFzRTV0ZG5GdFh6VXdzdUx1VUZKZA$aedwjQuTRuEzS9U0nHkGxCpkVdiqDHB/qag0MdagWzY', 'Guía 2', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'HOTEL_LOS_TAJIBOS', 'Hotel Los Tajibos', 'Hotel de cinco estrellas en Equipetrol, rodeado de jardines tropicales con tajibos. Piscinas, spa, gimnasio y centro de convenciones. Ofrecido por SczTourBo mediante convenio con el hotel.', 'Equipetrol', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Av. San Martín 455, Equipetrol', -17.763900, -63.195300, 5, '15:00', '12:00', '["Wi-Fi", "Piscina", "Desayuno incluido", "Estacionamiento", "Aire acondicionado", "Gimnasio", "Restaurante", "Spa", "Recepción 24 h", "Bar", "Traslado al aeropuerto", "Sala de eventos"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'DELUXE_KING', 'Deluxe King', 'Cama king, vista a los jardines.', 'Equipetrol', 950.00, 3, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 60, 2, 1, '1 cama king', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'DELUXE_TWIN', 'Deluxe Twin', 'Dos camas dobles, ideal para familias.', 'Equipetrol', 950.00, 4, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 50, 3, 2, '2 camas dobles', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'CLUB_KING', 'Club King', 'Acceso al lounge ejecutivo y desayuno a la carta.', 'Equipetrol', 1250.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 20, 2, 0, '1 cama king', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'JUNIOR_SUITE', 'Junior Suite', 'Sala de estar y terraza privada.', 'Equipetrol', 1600.00, 3, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 8, 2, 1, '1 cama king y sofá cama', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'SUITE_PRESIDENCIAL', 'Suite Presidencial', 'La suite más amplia del hotel, con comedor y jacuzzi.', 'Equipetrol', 3500.00, 4, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 1, 2, 2, '1 cama king', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'CITY_TOUR_SANTA_CRUZ_DE_LA_SIERRA', 'City Tour Santa Cruz de la Sierra', 'Recorrido por la Plaza 24 de Septiembre, la Catedral, el Casco Viejo y el Parque Urbano. Incluye transporte y guía.', 'Casco Viejo', 180.00, 15, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'LOMAS_DE_ARENA', 'Lomas de Arena', 'Excursión a las dunas del Parque Regional Lomas de Arena con lagunas y avistamiento de aves.', 'Parque Regional Lomas de Arena', 250.00, 12, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Samaipata'), v_moneda, 'FUERTE_DE_SAMAIPATA_Y_VALLES', 'Fuerte de Samaipata y Valles', 'Día completo al sitio arqueológico preincaico declarado Patrimonio de la Humanidad, con almuerzo en el pueblo de Samaipata.', 'Fuerte de Samaipata', 420.00, 12, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'NOCHE_CRUCENA_CON_SHOW_FOLCLORICO', 'Noche Cruceña con Show Folclórico', 'Cena típica (majadito, locro, cuñapé) con música y danzas del oriente boliviano.', 'Equipetrol', 230.00, 40, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'AVISTAMIENTO_DE_AVES_EN_EL_JARDIN_BOTANICO', 'Avistamiento de Aves en el Jardín Botánico', 'Recorrido temprano con guía especializado por el Jardín Botánico de Santa Cruz.', 'Jardín Botánico', 150.00, 10, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'PAQUETE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'SANTA_CRUZ_3D2N_CON_LOS_TAJIBOS', 'Santa Cruz 3D/2N con Los Tajibos', 'Dos noches en Hotel Los Tajibos con desayuno, City Tour y traslados aeropuerto-hotel.', 'Equipetrol', 2900.00, 4, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'PAQUETE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Samaipata'), v_moneda, 'SAMAIPATA_EXPRESS_2D1N', 'Samaipata Express 2D/1N', 'Transporte, una noche en Samaipata, visita al Fuerte y caminata a La Pajcha.', 'Samaipata', 1100.00, 8, 'BORRADOR') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Gustu (Solo restaurante)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Gustu') THEN
    v_sub := 'gustu'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'gustu' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), 'Gustu', 'Gustu', v_sub, 'contacto@gustu.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@gustu.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@gustu.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$S01nSkNLeXBWbURjcWR1UVlUU040Ng$1OhCKLgK/yUvXwQ2D2JqFyRzuB7WK2rvYi+Ud4pOifo', 'Jefe Admin', 'Gustu', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'CAJERO', 'Cajero', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@gustu.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@gustu.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$VjNBYkVUUVFRYjBPVGRnS1NlaUcxQQ$TlbhVkxW2FaJisR48PCjloZwoCUw/2YvDaBrr7XeLR4', 'Empleado 1', 'Gustu', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'CAJERO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'GUSTU', 'Gustu', 'Restaurante de alta cocina boliviana en Calacoto. Menú degustación con ingredientes de todo el país: amazonía, valles y altiplano.', 'Calacoto - Zona Sur', 650.00, 45, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Paceña La Salteña (Cadena gastronómica)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Paceña La Salteña') THEN
    v_sub := 'pacena-la-saltena'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'pacena-la-saltena' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), 'Paceña La Salteña', 'Paceña La Salteña', v_sub, 'contacto@pacenalasaltena.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'PROFESIONAL';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@pacenalasaltena.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@pacenalasaltena.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$MFZsUXoxWGNtZGdQcXhJUG1GbDFEaA$BSsNeaxROH76Ed68Gpgt7XcXhUI50ga7SZVL3uLZehk', 'Jefe Admin', 'Paceña La Salteña', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'CAJERO', 'Cajero', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@pacenalasaltena.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@pacenalasaltena.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Z2lEVXZ5R2EwSkRKc0ZneE01S0VoVg$M33Sg5l50ldVM2WWwpy6Iu/vBytpzvpt4PX08V2kkHQ', 'Empleado 1', 'Paceña La Salteña', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'CAJERO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@pacenalasaltena.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@pacenalasaltena.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$S0dmQWVJUWRQMGZ5S1lITUxKV2RTag$Dr4i0N/9NqQFHBLyvLq1CdOpKZNDLe8tEOnfXz1i/Xs', 'Empleado 2', 'Paceña La Salteña', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'CAJERO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'PACENA_LA_SALTENA_SOPOCACHI', 'Paceña La Salteña - Sopocachi', 'Salteñas jugosas de carne y pollo, recién horneadas cada mañana.', 'Sopocachi', 25.00, 60, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'PACENA_LA_SALTENA_CALACOTO', 'Paceña La Salteña - Calacoto', 'La salteña paceña de siempre en la Zona Sur, con postres y api.', 'Calacoto - Zona Sur', 25.00, 50, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'PACENA_LA_SALTENA_CENTRO', 'Paceña La Salteña - Centro', 'Sucursal a pasos de la Plaza Murillo, ideal para el desayuno paceño.', 'Centro', 25.00, 40, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'PACENA_LA_SALTENA_MIRAFLORES', 'Paceña La Salteña - Miraflores', 'Sucursal cerrada temporalmente por remodelación.', 'Miraflores', 25.00, 35, 'INACTIVO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Casa del Camba (Solo restaurante)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Casa del Camba') THEN
    v_sub := 'casa-del-camba'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'casa-del-camba' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), 'Casa del Camba', 'Casa del Camba', v_sub, 'contacto@casadelcamba.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@casadelcamba.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@casadelcamba.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RDVRT0ZyZ04wRU0zTkRxZDY2MTVpNg$591nOGnf8itHDLeH70tNBCrx7dUoIF4zZKZxRCawmMM', 'Jefe Admin', 'Casa del Camba', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'CAJERO', 'Cajero', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@casadelcamba.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@casadelcamba.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$ME40RmdjMXNNTnlYTnVZN3BEMmdSTA$hAJrcDSUeqLJjrlILKlc04cumJCjs1QnCVf3ayz+w5s', 'Empleado 1', 'Casa del Camba', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'CAJERO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Santa Cruz de la Sierra'), v_moneda, 'CASA_DEL_CAMBA', 'Casa del Camba', 'Comida típica cruceña y parrilla en un ambiente de casona oriental, con música en vivo los fines de semana.', 'Av. Cristóbal de Mendoza', 90.00, 200, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Casa de Campo (Solo restaurante)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Casa de Campo') THEN
    v_sub := 'casa-de-campo'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'casa-de-campo' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Cochabamba'), 'Casa de Campo', 'Casa de Campo', v_sub, 'contacto@casadecampo.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@casadecampo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@casadecampo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TklkNWNtdEowY2dVOVJhSFNBeHM3WA$ua0P5XC7Z+7RIMswpF8sNeASSMD0jrTMR66t7tvj8wI', 'Jefe Admin', 'Casa de Campo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'CAJERO', 'Cajero', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@casadecampo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@casadecampo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Q0pmdWFhdDRrbklHeHNlYk1kQXZZbg$kQ8LbOg+uRKYHbDDmtVWmOYN5YpEJUhLtXa4M9z/CGk', 'Empleado 1', 'Casa de Campo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'CAJERO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'RESTAURANTE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Cochabamba'), v_moneda, 'CASA_DE_CAMPO', 'Casa de Campo', 'Cocina cochabambina tradicional: pique macho, silpancho y chicharrón, en patio al aire libre.', 'Recoleta', 70.00, 150, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Gravity Bolivia (Tours y experiencias de aventura)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Gravity Bolivia') THEN
    v_sub := 'gravity-bolivia'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'gravity-bolivia' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), 'Gravity Bolivia', 'Gravity Bolivia', v_sub, 'contacto@gravitybolivia.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'PROFESIONAL';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@gravitybolivia.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$bkpvNjdQN2tSWml3WnFscjQzN2pqWA$ikCh6kekgYDtzg3jKfE/lnCE0AMoPOG7fcM7ylPaaGI', 'Jefe Admin', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'ENCARGADO_CATALOGO', 'Encargado de catálogo', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'PRODUCTOS_GESTIONAR', 'DISPONIBILIDAD_GESTIONAR', 'REPORTES_TENANT');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@gravitybolivia.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$bFBkUzg0aDlJbDNqdzd5NGtwREVvcQ$UGT4JtuEW0UI6HL6mnZ0dxBwQmRk7AAeM8ZmKbGj4xg', 'Empleado 1', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'ENCARGADO_CATALOGO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@gravitybolivia.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Z3hVM3BnbVlxUEhidEhhaWhsUEFQVA$b7qvpcksrqd9EsUOdz7g13FiZUr8OlVPYtxLhGalYv0', 'Guía 1', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@gravitybolivia.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TGpKT0pnamZ6M0VpaU9JSWNmNWNXYw$KdhEdvqnw0Lp92KziGyksZm6gSoT6wfVLAjtqBmDPwI', 'Guía 2', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'DESCENSO_EN_BICICLETA_POR_EL_CAMINO_DE_LA_MUERTE', 'Descenso en Bicicleta por el Camino de la Muerte', '64 km de descenso desde La Cumbre (4.700 m) hasta los Yungas. Incluye bicicleta de doble suspensión, equipo de protección, guías y almuerzo.', 'Yungas - Camino de la Muerte', 850.00, 12, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'BICI_DE_MONTANA_EN_CHACALTAYA', 'Bici de Montaña en Chacaltaya', 'Ruta de descenso desde el nevado Chacaltaya con vistas a la Cordillera Real.', 'Chacaltaya', 750.00, 10, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'RUTA_EN_BICICLETA_A_SORATA', 'Ruta en Bicicleta a Sorata', 'Dos días de pedaleo por caminos de altura hasta el valle de Sorata.', 'Sorata', 1400.00, 8, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'TIROLESA_EN_LOS_YUNGAS', 'Tirolesa en los Yungas', 'Tres tramos de tirolesa sobre la selva de los Yungas, al final del Camino de la Muerte.', 'Yolosa - Yungas', 320.00, 20, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Red Cap Walking Tours (Tours a pie (empresa suspendida))
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Red Cap Walking Tours') THEN
    v_sub := 'red-cap-walking-tours'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'red-cap-walking-tours' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), 'Red Cap Walking Tours', 'Red Cap Walking Tours', v_sub, 'contacto@redcapwalkingtours.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@redcapwalkingtours.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@redcapwalkingtours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TE9zYTBQQ01KYnBxZWtuYm5WaVh5Tw$B49Aiv6RBZpu2KZbpnYI4gE4L8stSMRQLZ0KTPMlfA4', 'Jefe Admin', 'Red Cap Walking Tours', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@redcapwalkingtours.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@redcapwalkingtours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$YTZlY2FlNHJ5RTA4cVd6dnJoS1A1Sg$BL88mQY5p5JNkeolieqJIRN2evYRXeuy/4aGpU4C+tA', 'Guía 1', 'Red Cap Walking Tours', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@redcapwalkingtours.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@redcapwalkingtours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$WFBEVEN6S3lKMlN1a0xKZUxheXEwcg$4O9A4C4XfK4v9iYfpnXCHvBPAeuhAm9fEVHnyj17Iws', 'Guía 2', 'Red Cap Walking Tours', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'WALKING_TOUR_POR_EL_CENTRO_DE_LA_PAZ', 'Walking Tour por el Centro de La Paz', 'Recorrido a pie por la Plaza Murillo, el Mercado Rodríguez y el Mercado de las Brujas con historias de la ciudad.', 'Centro', 70.00, 25, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'TELEFERICO_Y_MERCADO_DE_EL_ALTO', 'Teleférico y Mercado de El Alto', 'Viaje en teleférico hasta El Alto y visita a la feria 16 de Julio.', 'El Alto', 120.00, 20, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'La Paz'), v_moneda, 'LUCHA_LIBRE_DE_CHOLITAS', 'Lucha Libre de Cholitas', 'Función de lucha libre de cholitas en El Alto con transporte y bocadillos.', 'El Alto', 150.00, 30, 'PUBLICADO') RETURNING id INTO v_producto;
    UPDATE tenant SET estado = 'SUSPENDIDO' WHERE id = v_tenant;
    v_empresas := v_empresas + 1;
  END IF;

  -- Red Planet Expedition (Tours por el salar y paquetes)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Red Planet Expedition') THEN
    v_sub := 'red-planet-expedition'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'red-planet-expedition' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), 'Red Planet Expedition', 'Red Planet Expedition', v_sub, 'contacto@redplanetexpedition.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'PROFESIONAL';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@redplanetexpedition.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$ckpzUlhKVm1uZE5JSlY1Sk52TnBVZQ$sBlmmTMVcOWXg5Z+eygElu7xJWYOwJoHkEq9ZhfldVk', 'Jefe Admin', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@redplanetexpedition.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dHNMN0RlR3Z6NzVnMlp3bkM4d1NmaA$MKY3VzoIz5Gu69MttPhd2lV50Zw0x8F9tQKhT2mxpH8', 'Empleado 1', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@redplanetexpedition.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$UUZHVnVaYWNGdWY4VVRFZjBJZVY3dw$SjTv5ZNu68WMvZy4aOaeeX5Ru00l3HRsUbVivnER2Ps', 'Guía 1', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@redplanetexpedition.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RXV3ZGtmUE1nb1liNjhzRWNOVGhDOQ$zXBSn2bbxXo/J2UfDoXccKl759Xifr43PHjBo5dHkQ4', 'Guía 2', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'SALAR_DE_UYUNI_DIA_COMPLETO', 'Salar de Uyuni Día Completo', 'Cementerio de trenes, Colchani, isla Incahuasi y fotos de perspectiva en el salar. Incluye almuerzo y vehículo 4x4.', 'Salar de Uyuni', 450.00, 6, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'TRAVESIA_3D2N_SALAR_Y_LAGUNAS_DE_COLORES', 'Travesía 3D/2N Salar y Lagunas de Colores', 'Salar de Uyuni, Laguna Colorada, géiseres Sol de Mañana y Laguna Verde, con alojamiento en refugios.', 'Reserva Eduardo Avaroa', 1800.00, 6, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'ATARDECER_Y_ESTRELLAS_EN_EL_SALAR', 'Atardecer y Estrellas en el Salar', 'Salida por la tarde para ver la puesta de sol y el cielo nocturno sobre el salar.', 'Salar de Uyuni', 380.00, 6, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'AMANECER_EN_EL_ESPEJO_DEL_SALAR', 'Amanecer en el Espejo del Salar', 'En época de lluvias, salida antes del amanecer al efecto espejo del salar.', 'Salar de Uyuni', 400.00, 6, 'BORRADOR') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'PAQUETE'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Uyuni'), v_moneda, 'UYUNI_3D2N_CON_HOTEL_PALACIO_DE_SAL', 'Uyuni 3D/2N con Hotel Palacio de Sal', 'Dos noches en el Hotel Palacio de Sal, tour de día completo al salar y atardecer. El hotel se reserva a través de su propia empresa.', 'Salar de Uyuni', 3600.00, 4, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Madidi Jungle Ecolodge (Ecolodge con tours de selva)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Madidi Jungle Ecolodge') THEN
    v_sub := 'madidi-jungle-ecolodge'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'madidi-jungle-ecolodge' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Rurrenabaque'), 'Madidi Jungle Ecolodge', 'Madidi Jungle Ecolodge', v_sub, 'contacto@madidijungle.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'PROFESIONAL';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@madidijungle.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@madidijungle.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$ZnA1aUtGQVlYVm4ya0h1c0xQU1dXYg$WnkMPC/isYYLhCikDgOsfCXV0S0GfJ27fsKBw6avm+g', 'Jefe Admin', 'Madidi Jungle Ecolodge', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    INSERT INTO rol (id_tenant, codigo, nombre, ambito, es_sistema)
    VALUES (v_tenant, 'RECEPCIONISTA', 'Recepcionista', 'TENANT', FALSE) RETURNING id INTO v_rol;
    INSERT INTO rol_permiso (id_rol, id_permiso)
    SELECT v_rol, id FROM permiso WHERE codigo IN ('PRODUCTOS_LEER', 'DISPONIBILIDAD_GESTIONAR', 'RESERVAS_LEER', 'RESERVAS_GESTIONAR');
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@madidijungle.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@madidijungle.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$alBZcjBZVW5lbWFxWXdESU5lVTMwNA$CIBpC1MQVBUfeM/vG8HXpnGU6mt5joxN48SiQpPY+2M', 'Empleado 1', 'Madidi Jungle Ecolodge', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@madidijungle.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@madidijungle.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$MXNUTVdoWmFodkFRbjVLSG0yR2tyQg$wh9b4BL8EUu2LyNnE8x7CYSkSyS5it7WnkBdw1rsiDU', 'Guía 1', 'Madidi Jungle Ecolodge', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HOTEL'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Rurrenabaque'), v_moneda, 'MADIDI_JUNGLE_ECOLODGE', 'Madidi Jungle Ecolodge', 'Ecolodge comunitario dentro del Parque Nacional Madidi, gestionado por la comunidad de San José de Uchupiamonas. Se llega en bote por el río Beni y el río Tuichi desde Rurrenabaque.', 'Parque Nacional Madidi - San José de Uchupiamonas', 0, 1, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, direccion, latitud, longitud, categoria_estrellas, hora_check_in, hora_check_out, servicios)
    VALUES (v_producto, v_tenant, (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'), 'Río Tuichi, Parque Nacional Madidi', -14.623300, -67.971900, 2, '12:00', '10:00', '["Desayuno incluido", "Restaurante", "Traslado al aeropuerto"]'::jsonb) RETURNING id INTO v_hotel;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Rurrenabaque'), v_moneda, 'CABANA_DOBLE', 'Cabaña Doble', 'Cabaña de madera con mosquiteros y baño privado. Pensión completa.', 'Parque Nacional Madidi - San José de Uchupiamonas', 900.00, 2, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 6, 2, 0, '1 cama matrimonial', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'HABITACION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Rurrenabaque'), v_moneda, 'CABANA_FAMILIAR', 'Cabaña Familiar', 'Cabaña amplia para familias. Pensión completa.', 'Parque Nacional Madidi - San José de Uchupiamonas', 1300.00, 4, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO habitacion (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos, tipo_cama, incluye_desayuno)
    VALUES (v_producto, v_hotel, v_tenant, 3, 3, 2, '1 cama matrimonial y 2 individuales', TRUE);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Rurrenabaque'), v_moneda, 'EXPEDICION_3D2N_EN_EL_PARQUE_MADIDI', 'Expedición 3D/2N en el Parque Madidi', 'Caminatas por la selva, collpa de guacamayos y pesca artesanal con guías de la comunidad.', 'Parque Nacional Madidi', 2400.00, 8, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'TOUR'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Rurrenabaque'), v_moneda, 'PAMPAS_DEL_YACUMA_3D2N', 'Pampas del Yacuma 3D/2N', 'Navegación por el río Yacuma para ver delfines rosados, caimanes y capibaras.', 'Pampas del Yacuma', 1900.00, 8, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Rurrenabaque'), v_moneda, 'CAMINATA_NOCTURNA_EN_LA_SELVA', 'Caminata Nocturna en la Selva', 'Salida guiada al anochecer para descubrir insectos, ranas y aves nocturnas.', 'Parque Nacional Madidi', 250.00, 8, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Bodegas Kohlberg (Experiencias de vino y singani)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Bodegas Kohlberg') THEN
    v_sub := 'bodegas-kohlberg'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'bodegas-kohlberg' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Tarija'), 'Bodegas Kohlberg', 'Bodegas Kohlberg', v_sub, 'contacto@kohlberg.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@kohlberg.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@kohlberg.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$QUllUkt1bVNQZGRsYXROQTdVYlNyWQ$AxFZE3fo9dKY1g42/JNlY/xhMxS6syFAZGvjCVE1ACc', 'Jefe Admin', 'Bodegas Kohlberg', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@kohlberg.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@kohlberg.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$c0NFZkQ1b2lmRGdRTlNWeHBXSlBzNQ$N4sznClZ4EF+XGEVVfuh4ZJofA6GitCXms+iYH2VEBk', 'Empleado 1', 'Bodegas Kohlberg', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Tarija'), v_moneda, 'VISITA_Y_CATA_EN_BODEGAS_KOHLBERG', 'Visita y Cata en Bodegas Kohlberg', 'Recorrido por la bodega en Santa Ana y cata de vinos de altura con quesos tarijeños.', 'Santa Ana', 120.00, 25, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Tarija'), v_moneda, 'RUTA_DEL_VINO_Y_SINGANI', 'Ruta del Vino y Singani', 'Día completo por bodegas y viñedos del Valle Central de Tarija con almuerzo campestre.', 'Valle Central', 380.00, 15, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Parque Cretácico (Atracción)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Parque Cretácico') THEN
    v_sub := 'parque-cretacico'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'parque-cretacico' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), 'Parque Cretácico', 'Parque Cretácico', v_sub, 'contacto@parquecretacico.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@parquecretacico.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@parquecretacico.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TXoyczNMdFFlZldZWWNRcm1keVZReQ$TmKjYtfJNzKmg2dNGIF4itTx5JwT5x/X0Bs8HezNTgs', 'Jefe Admin', 'Parque Cretácico', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@parquecretacico.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@parquecretacico.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dlNudENkS0FRZzBQV3k1dVBjcHNUcg$Npy1yJcJghSryyTjsRkaHNI8N4QaqeYmznmF09scLW4', 'Empleado 1', 'Parque Cretácico', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'ATRACCION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), v_moneda, 'PARQUE_CRETACICO_CAL_ORCKO', 'Parque Cretácico - Cal Orck''o', 'Parque temático con réplicas de dinosaurios y mirador al muro con más de 5.000 huellas del período Cretácico.', 'Cal Orck''o', 50.00, 300, 'PUBLICADO') RETURNING id INTO v_producto;
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'EXPERIENCIA'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Sucre'), v_moneda, 'CAMINATA_GUIADA_AL_MURO_DE_HUELLAS', 'Caminata Guiada al Muro de Huellas', 'Bajada guiada con casco hasta el pie del muro de huellas (horarios limitados).', 'Cal Orck''o', 40.00, 25, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Casa Nacional de Moneda (Atracción)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Casa Nacional de Moneda') THEN
    v_sub := 'casa-nacional-de-moneda'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'casa-nacional-de-moneda' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Potosí'), 'Casa Nacional de Moneda', 'Casa Nacional de Moneda', v_sub, 'contacto@casadelamoneda.com.bo', 'ACTIVO') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@casadelamoneda.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@casadelamoneda.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$NWl5T2pYMWpva3ozVkpxd3MxYmNtcw$pIcKuUIWRHpyTKLLvDLA1lMeRgGpwLbmuNb+KmJR5YM', 'Jefe Admin', 'Casa Nacional de Moneda', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@casadelamoneda.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@casadelamoneda.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$YkhCM2I2cW5yTUMzendLOFpwQjZQUg$6e6/OLWDOjt1XQ8efHp9IcFIc3bpc3uzuvzs+GVCQ+4', 'Empleado 1', 'Casa Nacional de Moneda', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    INSERT INTO producto_turistico (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, descripcion, localidad, precio_base, capacidad_maxima, estado)
    VALUES (v_tenant, (SELECT id FROM tipo_producto WHERE codigo = 'ATRACCION'), (SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Potosí'), v_moneda, 'MUSEO_CASA_NACIONAL_DE_MONEDA', 'Museo Casa Nacional de Moneda', 'Edificio colonial donde se acuñó la plata del Cerro Rico. Visita guiada por las salas de laminación, pintura colonial y numismática.', 'Centro Histórico', 50.00, 150, 'PUBLICADO') RETURNING id INTO v_producto;
    v_empresas := v_empresas + 1;
  END IF;

  -- Tupiza Tours (Autorregistro pendiente de activación)
  IF NOT EXISTS (SELECT 1 FROM tenant WHERE nombre_comercial = 'Tupiza Tours') THEN
    v_sub := 'tupiza-tours'; v_n := 2;
    WHILE EXISTS (SELECT 1 FROM tenant WHERE subdominio = v_sub) LOOP
      v_sub := 'tupiza-tours' || '-' || v_n; v_n := v_n + 1;
    END LOOP;
    INSERT INTO tenant (id_ciudad, razon_social, nombre_comercial, subdominio, email_contacto, estado)
    VALUES ((SELECT id FROM ciudad WHERE id_pais = v_pais AND nombre = 'Tupiza'), 'Tupiza Tours', 'Tupiza Tours', v_sub, 'contacto@tupizatours.com.bo', 'PENDIENTE') RETURNING id INTO v_tenant;
    INSERT INTO suscripcion (id_tenant, id_plan, fecha_inicio, estado, renovacion_automatica, precio_contratado, id_moneda_contratada, periodicidad_contratada)
    SELECT v_tenant, p.id, CURRENT_DATE, 'ACTIVA', FALSE, p.precio_mensual, p.id_moneda, p.periodicidad
      FROM plan p WHERE p.codigo = 'BASICO';
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'jefeadmin@tupizatours.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('jefeadmin@tupizatours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$ODJsb3hYeGNEUk42ZFY1QTZlWjBhUA$/UOrFs709fkAkzkImcPnpcO8Hac24CZkC5GbiZJGT2M', 'Jefe Admin', 'Tupiza Tours', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_empresas := v_empresas + 1;
  END IF;

  -- Turistas
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista1@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista1@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$WGFTNnZ0MVRBbkY4aExOazlDU3MxTg$DX01cqGtPPId6BaDagNOoVIdjXSm9yIHrvkfcJYS4Pw', 'Lucía', 'Fernández Rojas', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista2@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista2@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$OFIyNE9Td1l6UmJXQWFDNmZrRjNSQg$FhuOrtI5IKIxhJfBQU34eLXy9rN4pM0vKw4F5zAZlFY', 'Martín', 'Gutiérrez Vaca', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista3@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista3@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$VGpSTTVlQVRzdEtzSTZJMDdZNmxxTg$t9zBX4p5GtAwsUiKQID89rpRJs8IzcJy44M4p4C1boM', 'Camila', 'Mamani Quispe', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista4@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista4@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$VUJUVmVtTVdoYklFbUgwam0xbnRnNQ$fh5NjIuiFR5u3qk0P4a7OZ6TmwawPyDU6vFx903fXBQ', 'Diego', 'Torrez Salvatierra', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;

  INSERT INTO bitacora (accion, entidad, datos_nuevos)
  VALUES ('SEED_DEMO', 'seed_bolivia', jsonb_build_object('empresas', v_empresas, 'turistas', v_turistas));
  RAISE NOTICE 'SITUR-SMART: % empresas y % turistas creados', v_empresas, v_turistas;
END
$seed$;
