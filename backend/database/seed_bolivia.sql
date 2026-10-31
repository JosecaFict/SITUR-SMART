-- ============================================================
-- SITUR-SMART: datos de demostracion de Bolivia
-- Generado con: python manage.py seed_bolivia --sql
-- No editar a mano: los datos viven en backend/apps/catalog/seed/bolivia.py
--
-- Contrasena de todas las cuentas: Admin123* (aqui viaja cifrada).
-- Se puede ejecutar mas de una vez: las empresas que ya existen se omiten y a los
-- tours solo se les suman las salidas de las semanas que falten.
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
      VALUES ('jefeadmin@hotelcortez.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RTN0NXFoN2lRMGJPSUFHUERndFFqOQ$ogdxJDRn612Xsbe8CZt9KEiDXyJTSeRLJU0T0vWOlbA', 'Jefe Admin', 'Hotel Cortez', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@hotelcortez.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Mnc1Z2V3ZnB6enV2ZFVQeFVQcGoweg$+IxcuLyj31MGSMX0FEem48idhbzx87m47aGZHuhNqTY', 'Empleado 1', 'Hotel Cortez', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@hotelcortez.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@hotelcortez.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$bHc2emxSZ0thNGxzMk1HakxJZjEzaQ$VsUv3mCTpgoMnnRDLsaF1wtShlZqApnLcgQzHt+Toms', 'Empleado 2', 'Hotel Cortez', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@hotelcupula.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Q2M0VEVMZHJlSFlPV2tSczRYc1ZxeA$lqzV5POEKNdN40YaVHCSEmStRrRP2PVeMS/9UOr+ax0', 'Jefe Admin', 'Hotel La Cúpula', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@hotelcupula.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RVBwbnNWUWYxUDhsbTJXUTRCbk5HWA$mxWCw4N3RqajTAK+Y+hX+nT+7n+/b/S6K7dKhAA7ij8', 'Empleado 1', 'Hotel La Cúpula', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$b1RyblZHYW5HY09jRGFqeHl6WG5acg$vBfnClx+1v4vU5tJxXwXRVpfo0n4KU8Kc8oSxVtk+Dg', 'Jefe Admin', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$UGNrQzNVVUJhZFpLTmFzRnhuS0c5Mg$cjHloSXK9VZFs4Eb4fOc9r3fJk1EDnc4WD3NQR/eq5s', 'Empleado 1', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@hotelesrosario.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dTNVMUl1dTBUOHRqeUNJVW5rU0RJMw$dJdGpBdCotDXGoyKTLDyfQNFP0LFFaw1hIMaEJIB6g4', 'Empleado 2', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado3@hotelesrosario.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado3@hotelesrosario.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$aGR3aU50MmxJMk55blFMYVZvYUtLVw$F5n6kcPM3ibbRnKX+KMBMLwcBCMp7NrnioSqxSoB/Dg', 'Empleado 3', 'Hoteles Rosario', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@palaciodesal.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dUdIUlZPZlpwQlZva1VWb0hpTndLNg$mHmA4kgCDLCWq0lXqUkH7iRaDVJy+HLO4vX7O+BFK40', 'Jefe Admin', 'Hotel Palacio de Sal', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@palaciodesal.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$aEVQUUp6QWU0QkRsUU9hVFJ0dExWTw$ZiFxi+0WGlQffGkwIfMcVw1EXflji1Yi7Z3Bd9C9zQE', 'Empleado 1', 'Hotel Palacio de Sal', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@palaciodesal.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@palaciodesal.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Slp6ZGtmNTQwYktJVHJmQ0VoREx5Yw$bW2jGzHkWs6FuZPGzllU/XuEDhII9Ym7E+h7OmQ6qnQ', 'Empleado 2', 'Hotel Palacio de Sal', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@paradorsantamaria.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$VjJCekI2MmM3NElWZU8xU2RQR011cw$73OJT+8FMVBd9aquOWlJZNppWuY4/gVkHIkumSsQNc4', 'Jefe Admin', 'Parador Santa María La Real', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@paradorsantamaria.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RGNLMm1UMjh6bDR1QzZiUG1YNkNPNg$AhW23HoZ36MNZ5hldN8AxKVvzDyTUWvpwT6oAIxluEQ', 'Empleado 1', 'Parador Santa María La Real', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Q0RvWU9DSXBqWFNDMUtIMVZ5d3BvUg$3Uo6WnjR3jLqlZun3z6uSR6IZF2giUjITHGN9arHWsU', 'Jefe Admin', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$bHZ2VkpZeGF6OXJmODFjbHFIQXdncg$KJiYrkHbDjv6ppFpu8CxuhuZ/0Cl/YSWa6AMt5ZLJUg', 'Empleado 1', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'ENCARGADO_CATALOGO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$YXVJY0xpWE1xVFZENHI2dmdFcldPOQ$QyHxqPOi4FufcPqSjMd8lahRGgGiF0yWOO5nLyAxG8g', 'Empleado 2', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$QnFPb1h6SERoWlpwNjdhNDEzaFpSTQ$9PYm3KIZ87FnuRtMqjHal2mXEYHmObeiT2wOO8Zacqw', 'Guía 1', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@scztourbo.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@scztourbo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$cFp4bUpweU9KTE01MkFEUTF6RWlKaA$/9L+YgvcvwlZgd+KTU+EXifJsrD5L3EuT24aGs8izuc', 'Guía 2', 'SczTourBo', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@gustu.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$YkZyTmxsWGdpc3dndzBIclhIeWpZcg$whLNlpTrVFpU6hc53nfJIacoofl+4ckIJ751a49zdOM', 'Jefe Admin', 'Gustu', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@gustu.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TkNwUDBFWmNIVTFXUnNsdEVENmkwZw$p26FJ6aZIf1fEWRY+qpNhUoCsqSXzhqOcKBd0fiEhDs', 'Empleado 1', 'Gustu', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@pacenalasaltena.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Yk5WdVdOZzU4eEN0WVlYVEtPOE5kYw$OCFPts9S/QTRHn+N/Sd9To2srbvjjQQhdPdt6pBJdXk', 'Jefe Admin', 'Paceña La Salteña', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@pacenalasaltena.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$bTUzY0g1S1EzM0NRSVBaZDZRbGNLYw$HgLU5wgZYbgqlqDltaZNoeX77xTu0+8LQ74mF/5db2g', 'Empleado 1', 'Paceña La Salteña', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'CAJERO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado2@pacenalasaltena.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado2@pacenalasaltena.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$aTgwaWpBNk1TSVJVTzF6VkpaNGxJaA$LLFKKLeZ9GdyqCrPUpP5AlUKezqEwdtG6C9rajjvgP0', 'Empleado 2', 'Paceña La Salteña', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@casadelcamba.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$MjJuTG5xOU52Rjg1Y0p3ZnVJcFR3OQ$6kgH2p0S1q8r5tbMP59QhLEiZFaWMA9RGUK5JPwrCww', 'Jefe Admin', 'Casa del Camba', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@casadelcamba.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$NXRJU0pldTloU1VGYnNrckpjdzg2Ng$VRjpj5Wp2XdPpvfLq0iGF7WYXIVmNnYGU2HvvwFXL/8', 'Empleado 1', 'Casa del Camba', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@casadecampo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$MldIQ2VENmJYWUZ0UTNjZDQ2aDVqSg$nDWCsb+azgrDQ2KHA0y5xzP16UGCLaCDdURhpuL8szQ', 'Jefe Admin', 'Casa de Campo', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@casadecampo.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$eFd0T1FjS3lhZzRyeTNaQ1ZmQklyQw$4ZzFMNDGthE8p91BMgLOFhLTohYDSXqLmntiOGAGCKo', 'Empleado 1', 'Casa de Campo', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dHlzcnRJdDNhMGRyZXhJa3E5VExLQg$OfZS+Cj45a41jmooFIHLGqps6fnld8QtvMYiz8/6M5Q', 'Jefe Admin', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$ZUN6UEFtbEwwbk85YXVuM1NGTFB4TQ$Qrz/cKV5EfWVWz4ehQ+qtdHRX3SZ5vWvZIfxQE6jSF4', 'Empleado 1', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'ENCARGADO_CATALOGO' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@gravitybolivia.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$THM2MUI1TWJvZHhJSUJ6VjZrek1PdQ$UVeSwx62NjTlMygnXTzfGCCFVsMUu9Na9+ul/ZYDaeA', 'Guía 1', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@gravitybolivia.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@gravitybolivia.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$eTBnMUhSWkNtWFdER2RlSFR5cDM1cQ$CWbiIP5YfBqti9OhqUa0Whs2CSRG4AprYbkcY4Zd6hs', 'Guía 2', 'Gravity Bolivia', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@redcapwalkingtours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$S2lya0ZXSnNEc1o4b2l2cFQybzRnYg$2TRt5ILUfaMbJQxL1wNNItaYERMWG66rAOjNUFSd7hg', 'Jefe Admin', 'Red Cap Walking Tours', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@redcapwalkingtours.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@redcapwalkingtours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$UHA0RnpESlhpSTN4ZzhSa3Y2MUowMg$zR705CgkgDV1ExmM6fNtlxSVpZmDmf8pm0JMjVjp3vw', 'Guía 1', 'Red Cap Walking Tours', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@redcapwalkingtours.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@redcapwalkingtours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RkJLRVJpaFE0YUNUNmQyMnYwNXMzQw$NF9BCbVho4CT2RV/s+XTeLgFsyYeC3GzUySJAEdCZ/A', 'Guía 2', 'Red Cap Walking Tours', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$THdVZU1KcGpmTWdFcWZXWFBEaXk5VA$H0349solr0l6zozgvzwfb01MoJlcvQ2AL8vvWX/0gt0', 'Jefe Admin', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@redplanetexpedition.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$RElvaVRmNDlLV1hyb09EYnZNWDRPVQ$VRPFsrofhBVimnuVdOSmLoUBp0xidlMP+Rx3IolRoiY', 'Empleado 1', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'TENANT_EMPLOYEE' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@redplanetexpedition.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TXN6Vkh3N2JTSVVsb0pUajBuZVRYaA$NJjrLrn7wMZwiAqtLVFffl4kqYvt83Na2UbZDMsog2c', 'Guía 1', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'GUIA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia2@redplanetexpedition.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia2@redplanetexpedition.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$dXV1VzYyVThPTEgydWRkUWU2NkZpag$QyNtT4ae7pAUA4p0QYYY1baBq7Ruv/4n90Rbc1Sc6bc', 'Guía 2', 'Red Planet Expedition', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@madidijungle.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$aVJhVUkyT0ZSTlRpdFYwdDA3RWcwdA$njNg6Kaj/MO/jse18PetAhjc3YOjAdr2gRiRO+iss3U', 'Jefe Admin', 'Madidi Jungle Ecolodge', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('empleado1@madidijungle.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$MUxteTlRRzF5QjJOYVpmWUlsMmFFZA$FptsQ2I9PiEiXbcPajo2qoA9n7QyA+DObPB2aueDlYU', 'Empleado 1', 'Madidi Jungle Ecolodge', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, (SELECT id FROM rol WHERE codigo = 'RECEPCIONISTA' AND ambito = 'TENANT' AND (id_tenant = v_tenant OR id_tenant IS NULL) ORDER BY id_tenant NULLS LAST LIMIT 1), v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'guia1@madidijungle.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('guia1@madidijungle.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$QmcyYkVlTHNsYm1ybmpOMmZGUTdQTw$ndDEHr2hWNXH8pjjn3dNUD2zSZoSCr0NLk/Il0mKbC4', 'Guía 1', 'Madidi Jungle Ecolodge', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@kohlberg.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$d0tBQjgyUkZrVGlrdVlNZjdUdFJSZQ$FTqXv+sKNNsv2Iw5xX58tkdrpEbqB5sQdzVyzVgq8kQ', 'Jefe Admin', 'Bodegas Kohlberg', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@kohlberg.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@kohlberg.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$ZFVuNTcxY1hGSE9JMTh6NTZuSEY1Vw$gb94C3LSb4sqQ6jXgXxxVQVFbnRSqecXxde023OgG18', 'Empleado 1', 'Bodegas Kohlberg', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@parquecretacico.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$VGdvNXhvd0dTa1JScXltc2ROSmFMZA$ryukwoyTs4MS2cNIRCrP7M+XLiterXAq4fcevcfPSzI', 'Jefe Admin', 'Parque Cretácico', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@parquecretacico.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@parquecretacico.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$a3hHUFJFcDB1aEc5Wm1lblhPc2MxVg$vBEUaLvK98VbnKDo8nvmmaDS9IIOLbSuVMvT6//H3h8', 'Empleado 1', 'Parque Cretácico', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@casadelamoneda.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$Q2VGM0x2MlY5Ykw4M3VLUEFrSHZPcA$UuQLLnUDd3sh22TwnSZ07ByVMNzGJSOthC2l/1jraGs', 'Jefe Admin', 'Casa Nacional de Moneda', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_user := NULL;
    SELECT id INTO v_user FROM usuario WHERE email = 'empleado1@casadelamoneda.com.bo';
    IF v_user IS NULL THEN
      INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
      VALUES ('empleado1@casadelamoneda.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$SmlFd3hST2hPcXdIRUlXWVRrS3JVeA$74Vjm21liR3Fi2W2WAzqJgY3yxozzi/MNIydnXXwp8s', 'Empleado 1', 'Casa Nacional de Moneda', 'ACTIVO') RETURNING id INTO v_user;
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
      VALUES ('jefeadmin@tupizatours.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$ZVlIMjJLOUNQdDZjaGk2ZGh6eUQwYw$P8ZROjR/gsphioBx12rXVb8Lu2yCt98Wg52NkEmAHng', 'Jefe Admin', 'Tupiza Tours', 'ACTIVO') RETURNING id INTO v_user;
    END IF;
    INSERT INTO usuario_tenant (id_usuario, id_tenant, estado) VALUES (v_user, v_tenant, 'ACTIVO')
      ON CONFLICT (id_usuario, id_tenant) DO UPDATE SET estado = 'ACTIVO';
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_admin, v_tenant);
    v_empresas := v_empresas + 1;
  END IF;

  -- Tours y experiencias (CU20): fichas, guias y salidas de las proximas semanas

  -- Tours de SczTourBo
  v_tenant := NULL; SELECT id INTO v_tenant FROM tenant WHERE nombre_comercial = 'SczTourBo' AND estado = 'ACTIVO';
  IF v_tenant IS NOT NULL THEN
    INSERT INTO guia (id_tenant, nombres, idiomas)
    SELECT v_tenant, 'Guía 1 SczTourBo', '["Español", "Inglés"]'::jsonb
    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 SczTourBo');
    INSERT INTO guia (id_tenant, nombres, idiomas)
    SELECT v_tenant, 'Guía 2 SczTourBo', '["Español", "Inglés"]'::jsonb
    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 SczTourBo');
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'City Tour Santa Cruz de la Sierra' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 240, 'Español e inglés', 'BAJA', NULL, 'Plaza 24 de Septiembre, frente a la Catedral', -17.783700, -63.182100, '["Transporte", "Guía", "Agua"]'::jsonb, '["Almuerzo"]'::jsonb, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Plaza 24 de Septiembre', NULL, 40);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Catedral Metropolitana', NULL, 30);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Casco Viejo', NULL, 45);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 4, 'Parque Urbano', NULL, 30);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '09:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '09:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '240 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 SczTourBo')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1, 2, 3, 4, 5, 6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Lomas de Arena' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 240, 'Español e inglés', 'MEDIA', NULL, 'Ingreso al Parque Regional Lomas de Arena', -17.901700, -63.145000, '["Transporte 4x4", "Guía"]'::jsonb, '["Tabla de sandboard"]'::jsonb, 'Protector solar, gorra y agua.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Dunas', 'Caminata y sandboard en las dunas', 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Laguna', NULL, 45);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Mirador de aves', NULL, 30);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '14:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '14:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '240 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 SczTourBo')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (2, 4, 6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Fuerte de Samaipata y Valles' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 660, 'Español e inglés', 'MEDIA', 6, 'Plaza principal de Samaipata', -18.178900, -63.875600, '["Transporte", "Guía", "Entrada al Fuerte", "Almuerzo"]'::jsonb, '["Bebidas"]'::jsonb, 'Zapatos cómodos para caminar.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Fuerte de Samaipata', NULL, 150);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Almuerzo en el pueblo', NULL, 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Mirador de los valles', NULL, 40);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '07:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '07:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '660 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 SczTourBo')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (3, 7)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Noche Cruceña con Show Folclórico' AND t.codigo = 'EXPERIENCIA';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 180, 'Español', 'BAJA', NULL, 'Restaurante del show, Equipetrol', -17.765000, -63.196000, '["Cena", "Show"]'::jsonb, '["Bebidas alcohólicas"]'::jsonb, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Cena típica', 'Majadito, locro y cuñapé', 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Show folclórico', NULL, 60);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '20:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '20:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '180 minutes', p.capacidad_maxima, NULL
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (5, 6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Avistamiento de Aves en el Jardín Botánico' AND t.codigo = 'EXPERIENCIA';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 180, 'Español e inglés', 'BAJA', 8, 'Ingreso al Jardín Botánico de Santa Cruz', -17.774500, -63.071800, '["Guía especializado", "Binoculares"]'::jsonb, '[]'::jsonb, 'Ropa de colores claros y repelente.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Sendero del bosque', NULL, 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Laguna', NULL, 45);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '06:30') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '06:30') AT TIME ZONE 'America/La_Paz') + INTERVAL '180 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 SczTourBo')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
  END IF;

  -- Tours de Gravity Bolivia
  v_tenant := NULL; SELECT id INTO v_tenant FROM tenant WHERE nombre_comercial = 'Gravity Bolivia' AND estado = 'ACTIVO';
  IF v_tenant IS NOT NULL THEN
    INSERT INTO guia (id_tenant, nombres, idiomas)
    SELECT v_tenant, 'Guía 1 Gravity Bolivia', '["Español", "Inglés"]'::jsonb
    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 Gravity Bolivia');
    INSERT INTO guia (id_tenant, nombres, idiomas)
    SELECT v_tenant, 'Guía 2 Gravity Bolivia', '["Español", "Inglés"]'::jsonb
    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 Gravity Bolivia');
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Descenso en Bicicleta por el Camino de la Muerte' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 600, 'Español e inglés', 'ALTA', 14, 'Oficina de Gravity Bolivia, calle Linares, La Paz', -16.497200, -68.139300, '["Bicicleta de doble suspensión", "Equipo de protección", "Guías", "Almuerzo", "Transporte de vuelta"]'::jsonb, '["Entrada al camino", "Propinas"]'::jsonb, 'Saber andar en bicicleta. Ropa abrigada y zapatos cerrados.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'La Cumbre (4.700 m)', NULL, 30);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Descenso en asfalto', NULL, 60);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Camino de la Muerte', NULL, 180);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 4, 'Almuerzo en Yolosa', NULL, 60);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '07:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '07:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '600 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 Gravity Bolivia')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1, 2, 3, 4, 5, 6, 7)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Bici de Montaña en Chacaltaya' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 480, 'Español e inglés', 'ALTA', 16, 'Oficina de Gravity Bolivia, calle Linares, La Paz', -16.497200, -68.139300, '["Bicicleta", "Equipo de protección", "Guía", "Refrigerio"]'::jsonb, '[]'::jsonb, 'Buena condición física: se pedalea sobre los 5.000 m.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Nevado Chacaltaya', NULL, 60);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Descenso', NULL, 150);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Valle de Zongo', NULL, 60);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '07:30') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '07:30') AT TIME ZONE 'America/La_Paz') + INTERVAL '480 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 Gravity Bolivia')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (2, 5)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Ruta en Bicicleta a Sorata' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 1980, 'Español e inglés', 'ALTA', 16, 'Oficina de Gravity Bolivia, calle Linares, La Paz', -16.497200, -68.139300, '["Bicicleta", "Guía", "Alojamiento una noche", "Comidas"]'::jsonb, '[]'::jsonb, 'Experiencia previa en rutas de varios días.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Salida desde La Paz', NULL, 30);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Achacachi', NULL, 60);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Valle de Sorata', NULL, 180);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '07:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '07:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '1980 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 Gravity Bolivia')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Tirolesa en los Yungas' AND t.codigo = 'EXPERIENCIA';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 120, 'Español e inglés', 'MEDIA', 10, 'Yolosa, base de la tirolesa', -16.231000, -67.748000, '["Arnés y casco", "Instructor"]'::jsonb, '["Transporte desde La Paz"]'::jsonb, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Primer tramo', NULL, 20);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Segundo tramo', NULL, 20);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Tercer tramo', NULL, 20);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '14:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '14:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '120 minutes', p.capacidad_maxima, NULL
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1, 2, 3, 4, 5, 6, 7)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
  END IF;

  -- Tours de Red Planet Expedition
  v_tenant := NULL; SELECT id INTO v_tenant FROM tenant WHERE nombre_comercial = 'Red Planet Expedition' AND estado = 'ACTIVO';
  IF v_tenant IS NOT NULL THEN
    INSERT INTO guia (id_tenant, nombres, idiomas)
    SELECT v_tenant, 'Guía 1 Red Planet Expedition', '["Español", "Inglés"]'::jsonb
    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 Red Planet Expedition');
    INSERT INTO guia (id_tenant, nombres, idiomas)
    SELECT v_tenant, 'Guía 2 Red Planet Expedition', '["Español", "Inglés"]'::jsonb
    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 Red Planet Expedition');
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Salar de Uyuni Día Completo' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 480, 'Español e inglés', 'BAJA', NULL, 'Oficina de Red Planet, Av. Ferroviaria, Uyuni', -20.460300, -66.825300, '["Vehículo 4x4", "Guía", "Almuerzo"]'::jsonb, '["Entrada a la isla Incahuasi"]'::jsonb, 'Lentes de sol, protector solar y abrigo.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Cementerio de trenes', NULL, 40);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Colchani', NULL, 45);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Isla Incahuasi', 'Cactus gigantes y vista al salar', 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 4, 'Fotos de perspectiva', NULL, 60);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '10:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '10:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '480 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 Red Planet Expedition')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1, 2, 3, 4, 5, 6, 7)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Travesía 3D/2N Salar y Lagunas de Colores' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 3270, 'Español e inglés', 'MEDIA', 6, 'Oficina de Red Planet, Av. Ferroviaria, Uyuni', -20.460300, -66.825300, '["Vehículo 4x4", "Guía", "Refugios", "Comidas"]'::jsonb, '["Entrada a la reserva"]'::jsonb, 'Abrigo para temperaturas bajo cero. Se recomienda bolsa de dormir.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Salar de Uyuni', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Laguna Colorada', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Géiseres Sol de Mañana', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 4, 'Laguna Verde', NULL, NULL);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '10:30') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '10:30') AT TIME ZONE 'America/La_Paz') + INTERVAL '3270 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 2 Red Planet Expedition')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1, 4)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Atardecer y Estrellas en el Salar' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 240, 'Español e inglés', 'BAJA', NULL, 'Oficina de Red Planet, Av. Ferroviaria, Uyuni', -20.460300, -66.825300, '["Vehículo 4x4", "Bebida caliente"]'::jsonb, '[]'::jsonb, 'Abrigo: de noche hace mucho frío.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Salar al atardecer', NULL, 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Observación de estrellas', NULL, 60);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '16:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '16:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '240 minutes', p.capacidad_maxima, NULL
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1, 2, 3, 4, 5, 6, 7)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Amanecer en el Espejo del Salar' AND t.codigo = 'EXPERIENCIA';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 180, 'Español e inglés', 'BAJA', NULL, 'Oficina de Red Planet, Av. Ferroviaria, Uyuni', -20.460300, -66.825300, '["Vehículo 4x4", "Botas de goma"]'::jsonb, '[]'::jsonb, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Efecto espejo al amanecer', NULL, 120);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
  END IF;

  -- Tours de Madidi Jungle Ecolodge
  v_tenant := NULL; SELECT id INTO v_tenant FROM tenant WHERE nombre_comercial = 'Madidi Jungle Ecolodge' AND estado = 'ACTIVO';
  IF v_tenant IS NOT NULL THEN
    INSERT INTO guia (id_tenant, nombres, idiomas)
    SELECT v_tenant, 'Guía 1 Madidi Jungle Ecolodge', '["Español", "Inglés"]'::jsonb
    WHERE NOT EXISTS (SELECT 1 FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 Madidi Jungle Ecolodge');
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Expedición 3D/2N en el Parque Madidi' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 3360, 'Español e inglés', 'MEDIA', 8, 'Muelle de Rurrenabaque, a orillas del río Beni', -14.441300, -67.527800, '["Lancha", "Guía de la comunidad", "Alojamiento", "Pensión completa"]'::jsonb, '[]'::jsonb, 'Repelente, ropa de manga larga y botas.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Navegación por el río Beni', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Collpa de guacamayos', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Caminata en la selva', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 4, 'Pesca artesanal', NULL, NULL);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '08:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '08:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '3360 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 Madidi Jungle Ecolodge')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Pampas del Yacuma 3D/2N' AND t.codigo = 'TOUR';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 3360, 'Español e inglés', 'BAJA', NULL, 'Muelle de Rurrenabaque, a orillas del río Beni', -14.441300, -67.527800, '["Transporte", "Lancha", "Guía", "Alojamiento", "Pensión completa"]'::jsonb, '["Entrada al área protegida"]'::jsonb, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Santa Rosa del Yacuma', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Río Yacuma', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Delfines rosados', NULL, NULL);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 4, 'Caimanes y capibaras', NULL, NULL);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '08:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '08:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '3360 minutes', p.capacidad_maxima, (SELECT id FROM guia WHERE id_tenant = v_tenant AND nombres = 'Guía 1 Madidi Jungle Ecolodge')
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (4)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Caminata Nocturna en la Selva' AND t.codigo = 'EXPERIENCIA';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 120, 'Español e inglés', 'BAJA', 10, 'Recepción de Madidi Jungle Ecolodge', -14.441300, -67.527800, '["Linterna frontal", "Guía"]'::jsonb, '[]'::jsonb, 'Botas y repelente.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Sendero de los insectos', NULL, 50);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Charca de las ranas', NULL, 40);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '19:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '19:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '120 minutes', p.capacidad_maxima, NULL
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (1, 2, 3, 4, 5, 6, 7)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
  END IF;

  -- Tours de Bodegas Kohlberg
  v_tenant := NULL; SELECT id INTO v_tenant FROM tenant WHERE nombre_comercial = 'Bodegas Kohlberg' AND estado = 'ACTIVO';
  IF v_tenant IS NOT NULL THEN
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Visita y Cata en Bodegas Kohlberg' AND t.codigo = 'EXPERIENCIA';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 120, 'Español', 'BAJA', 18, 'Bodegas Kohlberg, Santa Ana', -21.623000, -64.628000, '["Cata de 4 vinos", "Quesos tarijeños"]'::jsonb, '[]'::jsonb, 'La cata es solo para mayores de 18 años.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Viñedos', NULL, 30);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Bodega', NULL, 40);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Cata de vinos de altura', NULL, 50);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '10:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '10:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '120 minutes', p.capacidad_maxima, NULL
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (2, 3, 4, 5, 6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '15:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '15:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '120 minutes', p.capacidad_maxima, NULL
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (2, 3, 4, 5, 6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
    v_producto := NULL;
    SELECT p.id INTO v_producto FROM producto_turistico p JOIN tipo_producto t ON t.id = p.id_tipo_producto
     WHERE p.id_tenant = v_tenant AND p.nombre = 'Ruta del Vino y Singani' AND t.codigo = 'EXPERIENCIA';
    IF v_producto IS NOT NULL AND NOT EXISTS (SELECT 1 FROM detalle_tour WHERE id_producto = v_producto) THEN
      INSERT INTO detalle_tour (id_producto, id_tenant, duracion_minutos, idioma, dificultad, edad_minima, punto_encuentro, latitud, longitud, incluye, no_incluye, requisitos)
      VALUES (v_producto, v_tenant, 480, 'Español', 'BAJA', 18, 'Plaza Luis de Fuentes, Tarija', -21.535500, -64.729600, '["Transporte", "Catas", "Almuerzo"]'::jsonb, '[]'::jsonb, 'Solo para mayores de 18 años.');
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 1, 'Bodega Kohlberg', NULL, 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 2, 'Viñedos del Valle Central', NULL, 60);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 3, 'Almuerzo campestre', NULL, 90);
      INSERT INTO parada_tour (id_producto, id_tenant, orden, nombre, descripcion, duracion_minutos) VALUES (v_producto, v_tenant, 4, 'Destilería de singani', NULL, 60);
      UPDATE disponibilidad SET cerrado = TRUE WHERE id_producto = v_producto AND inicio > CURRENT_TIMESTAMP AND NOT cerrado;
    END IF;
    IF v_producto IS NOT NULL THEN
      INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total, id_guia)
      SELECT v_producto, v_tenant, ((g.d + TIME '09:00') AT TIME ZONE 'America/La_Paz'), ((g.d + TIME '09:00') AT TIME ZONE 'America/La_Paz') + INTERVAL '480 minutes', p.capacidad_maxima, NULL
        FROM producto_turistico p,
             generate_series(CURRENT_DATE + 1, CURRENT_DATE + 42, INTERVAL '1 day') AS g(d)
       WHERE p.id = v_producto AND EXTRACT(ISODOW FROM g.d) IN (6)
      ON CONFLICT (id_producto, inicio) DO NOTHING;
    END IF;
  END IF;

  -- Turistas
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista1@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista1@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$cUlHUzBicjZSVm9OUmNqd1Z4ZUd3Yg$ar7C0gIEXORdjUHjoOCGgVaegg3Icw1sqSe/kMdVgQA', 'Lucía', 'Fernández Rojas', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista2@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista2@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$TjFsbVhkd1N5YWtqZXZFUDdFT3NFZQ$Kp+BkJxLQGNsCjSi/i/8A8J3Hu8goWy4k9cAWksfCns', 'Martín', 'Gutiérrez Vaca', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista3@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista3@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$SW9rdENPWU1TbkNwaE5qd3J1U1FGUg$7mboSPE5vnDshUxhi7YdyGgQliV2hpLWZVtSJKX1oNY', 'Camila', 'Mamani Quispe', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM usuario WHERE email = 'turista4@situr.com.bo') THEN
    INSERT INTO usuario (email, password_hash, nombres, apellidos, estado)
    VALUES ('turista4@situr.com.bo', 'argon2$argon2id$v=19$m=102400,t=2,p=8$clR1Uk5aOWlMMnhNakxRQTA3Y0JnTg$RTZSMdNhEg0rcYihGsBdi2OjMxRmKhefBsRbqGw+oJY', 'Diego', 'Torrez Salvatierra', 'ACTIVO') RETURNING id INTO v_user;
    INSERT INTO usuario_rol (id_usuario, id_rol, id_tenant) VALUES (v_user, v_rol_cliente, NULL);
    INSERT INTO perfil_cliente (id_usuario) VALUES (v_user);
    v_turistas := v_turistas + 1;
  END IF;

  INSERT INTO bitacora (accion, entidad, datos_nuevos)
  VALUES ('SEED_DEMO', 'seed_bolivia', jsonb_build_object('empresas', v_empresas, 'turistas', v_turistas));
  RAISE NOTICE 'SITUR-SMART: % empresas y % turistas creados', v_empresas, v_turistas;
END
$seed$;
