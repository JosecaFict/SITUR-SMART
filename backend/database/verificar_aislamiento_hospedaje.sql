-- SITUR-SMART - Verificacion del aislamiento multitenant del modulo Hospedaje
--
-- Comprueba contra PostgreSQL la afirmacion central del diseno: que una
-- habitacion no puede colgarse del establecimiento de otra empresa. Esa regla
-- no vive en Python sino en dos claves foraneas compuestas que comparten la
-- columna id_tenant:
--
--     habitacion (id_producto,        id_tenant) -> producto_turistico(id, id_tenant)
--     habitacion (id_establecimiento, id_tenant) -> establecimiento_hospedaje(id, id_tenant)
--
-- Las pruebas de pytest no pueden verificar esto: corren sobre SQLite y los
-- modelos usan managed = False, asi que estas tablas no existen alli.
--
-- SEGURIDAD: todo ocurre dentro de una transaccion que termina en ROLLBACK. No
-- hay ningun COMMIT. Crea sus propios datos de prueba (dos empresas con
-- subdominio qa-aislamiento-*) y no los deja. Se puede correr sobre produccion
-- sin dejar rastro.
--
-- IMPORTANTE: ejecutar el ARCHIVO COMPLETO de una sola vez. Si se corre por
-- partes o se selecciona solo el bloque DO, el ROLLBACK final no se aplica y
-- las empresas de prueba quedan en la base.
--
-- Cada prueba usa su propio producto a proposito. La restriccion
-- uq_habitacion_producto UNIQUE (id_producto) impide dos habitaciones sobre el
-- mismo producto, y en PostgreSQL las claves foraneas se verifican como
-- triggers AFTER, es decir despues del indice unico: reutilizar un producto ya
-- usado haria fallar el INSERT por unique_violation antes de llegar a la clave
-- foranea, y la prueba reportaria un fallo que no existe.
--
-- Ejecutar DESPUES de que las migraciones 0004 y 0005 esten aplicadas.
-- Resultado esperado: cinco NOTICE que empiezan con "OK".
-- Cualquier "FALLO" significa que el aislamiento no esta garantizado.

BEGIN;

DO $$
DECLARE
    ciudad_id         BIGINT;
    moneda_id         BIGINT;
    tipo_hotel        BIGINT;
    tipo_habitacion   BIGINT;
    hospedaje_hotel   BIGINT;

    empresa_a         BIGINT;
    empresa_b         BIGINT;
    producto_hotel_a  BIGINT;
    producto_hotel_b  BIGINT;
    establecimiento_a BIGINT;
    establecimiento_b BIGINT;

    -- Un producto HABITACION por prueba, para que el indice unico no se cruce.
    hab_legitima      BIGINT;
    hab_cruzada       BIGINT;
    hab_check         BIGINT;

    habitacion_creada BIGINT;
BEGIN
    -- ---------- Datos de referencia que ya deben existir ----------
    SELECT id INTO ciudad_id FROM ciudad ORDER BY id LIMIT 1;
    SELECT id INTO moneda_id FROM moneda ORDER BY id LIMIT 1;
    SELECT id INTO tipo_hotel FROM tipo_producto WHERE codigo = 'HOTEL';
    SELECT id INTO tipo_habitacion FROM tipo_producto WHERE codigo = 'HABITACION';
    SELECT id INTO hospedaje_hotel FROM tipo_hospedaje WHERE codigo = 'HOTEL';

    IF ciudad_id IS NULL OR moneda_id IS NULL OR tipo_hotel IS NULL
       OR tipo_habitacion IS NULL OR hospedaje_hotel IS NULL THEN
        RAISE EXCEPTION
            'Faltan datos de catalogo (ciudad, moneda, tipo_producto o tipo_hospedaje). Verifica que 0004 este aplicada.';
    END IF;

    -- ---------- Dos empresas de prueba ----------
    INSERT INTO tenant (razon_social, nombre_comercial, subdominio, estado)
    VALUES ('QA Aislamiento A SRL', 'QA Hoteles A', 'qa-aislamiento-a', 'ACTIVO')
    RETURNING id INTO empresa_a;

    INSERT INTO tenant (razon_social, nombre_comercial, subdominio, estado)
    VALUES ('QA Aislamiento B SRL', 'QA Hoteles B', 'qa-aislamiento-b', 'ACTIVO')
    RETURNING id INTO empresa_b;

    -- ---------- Un hotel con su ficha en cada empresa ----------
    INSERT INTO producto_turistico
        (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, precio_base, capacidad_maxima, estado)
    VALUES (empresa_a, tipo_hotel, ciudad_id, moneda_id, 'QA_HOTEL_A', 'QA Hotel A', 0, 10, 'PUBLICADO')
    RETURNING id INTO producto_hotel_a;

    INSERT INTO producto_turistico
        (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, precio_base, capacidad_maxima, estado)
    VALUES (empresa_b, tipo_hotel, ciudad_id, moneda_id, 'QA_HOTEL_B', 'QA Hotel B', 0, 10, 'PUBLICADO')
    RETURNING id INTO producto_hotel_b;

    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje)
    VALUES (producto_hotel_a, empresa_a, hospedaje_hotel) RETURNING id INTO establecimiento_a;

    INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje)
    VALUES (producto_hotel_b, empresa_b, hospedaje_hotel) RETURNING id INTO establecimiento_b;

    -- ---------- Tres productos HABITACION de la empresa A ----------
    INSERT INTO producto_turistico
        (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, precio_base, capacidad_maxima, estado)
    VALUES (empresa_a, tipo_habitacion, ciudad_id, moneda_id, 'QA_HAB_1', 'QA Habitacion 1', 180, 2, 'PUBLICADO')
    RETURNING id INTO hab_legitima;

    INSERT INTO producto_turistico
        (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, precio_base, capacidad_maxima, estado)
    VALUES (empresa_a, tipo_habitacion, ciudad_id, moneda_id, 'QA_HAB_2', 'QA Habitacion 2', 190, 2, 'PUBLICADO')
    RETURNING id INTO hab_cruzada;

    INSERT INTO producto_turistico
        (id_tenant, id_tipo_producto, id_ciudad, id_moneda, codigo, nombre, precio_base, capacidad_maxima, estado)
    VALUES (empresa_a, tipo_habitacion, ciudad_id, moneda_id, 'QA_HAB_3', 'QA Habitacion 3', 200, 2, 'PUBLICADO')
    RETURNING id INTO hab_check;

    -- ============================================================
    -- 1. El caso legitimo debe funcionar
    -- ============================================================
    INSERT INTO habitacion
        (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos)
    VALUES (hab_legitima, establecimiento_a, empresa_a, 5, 2, 0)
    RETURNING id INTO habitacion_creada;
    RAISE NOTICE 'OK 1/5: una habitacion entra en el hotel de su propia empresa (id=%)', habitacion_creada;

    -- ============================================================
    -- 2. Habitacion de la empresa A apuntando al hotel de la empresa B.
    --    La FK (id_establecimiento, id_tenant) busca (establecimiento_b,
    --    empresa_a), que no existe: el establecimiento_b es de empresa_b.
    -- ============================================================
    BEGIN
        INSERT INTO habitacion
            (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos)
        VALUES (hab_cruzada, establecimiento_b, empresa_a, 1, 2, 0);
        RAISE EXCEPTION 'FALLO 2/5: se permitio colgar una habitacion del hotel de otra empresa';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'OK 2/5: PostgreSQL rechazo la habitacion cruzada entre empresas';
    END;

    -- ============================================================
    -- 3. Mentir sobre el tenant tampoco sirve. Si declara empresa_b para
    --    alcanzar el hotel de B, entonces la otra FK busca
    --    (hab_cruzada, empresa_b) y ese producto es de empresa_a.
    --    Las dos claves se cierran entre si.
    -- ============================================================
    BEGIN
        INSERT INTO habitacion
            (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos)
        VALUES (hab_cruzada, establecimiento_b, empresa_b, 1, 2, 0);
        RAISE EXCEPTION 'FALLO 3/5: se permitio declarar otro tenant para alcanzar un hotel ajeno';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'OK 3/5: cambiar el id_tenant tampoco permite el cruce';
    END;

    -- ============================================================
    -- 4. Un establecimiento inexistente se rechaza igual
    -- ============================================================
    BEGIN
        INSERT INTO habitacion
            (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos)
        VALUES (hab_cruzada, 9223372036854775807, empresa_a, 1, 2, 0);
        RAISE EXCEPTION 'FALLO 4/5: se permitio apuntar a un establecimiento inexistente';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'OK 4/5: un establecimiento inexistente se rechaza';
    END;

    -- ============================================================
    -- 5. Los CHECK de cantidad
    -- ============================================================
    BEGIN
        INSERT INTO habitacion
            (id_producto, id_establecimiento, id_tenant, cantidad_habitaciones, capacidad_adultos, capacidad_ninos)
        VALUES (hab_check, establecimiento_a, empresa_a, 0, 2, 0);
        RAISE EXCEPTION 'FALLO 5/5: se permitio cantidad_habitaciones = 0';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'OK 5/5: los CHECK rechazan cantidades invalidas';
    END;

    RAISE NOTICE '---';
    RAISE NOTICE 'Aislamiento multitenant verificado contra PostgreSQL.';
    RAISE NOTICE 'Lo que sigue es un ROLLBACK: no queda ningun dato de prueba.';
END $$;

-- Deshace absolutamente todo lo anterior, incluidas las dos empresas de prueba.
ROLLBACK;
