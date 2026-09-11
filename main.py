from datetime import date
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
from google import genai

# Importamos la configuración y modelos creados en database.py
from database import (
    SessionLocal, init_db, Usuario, MesPlanificado, 
    MetaMes, ActividadMes, RegistroActividadDiario, NotaDiario
)

# Inicializamos las tablas al arrancar
init_db()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Habit Tracker & Smart Journal API",
    description="Backend para gestión de hábitos, diario personal e integración con IA.",
    version="1.0.0"
)

# Permitir requests desde el archivo HTML local (file://) y localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# DEPENDENCIA DE BASE DE DATOS
# ==========================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# ESQUEMAS PYDANTIC (Validación de Datos)
# ==========================================
class UsuarioCreate(BaseModel):
    nombre: str
    email: str

class PlanificacionMesCreate(BaseModel):
    usuario_id: int
    anio: int
    mes: int
    metas: List[str]          # Lista de 3 metas
    actividades: List[str]      # Lista de 5 a 10 actividades diarias

class RegistroHabitoItem(BaseModel):
    actividad_mes_id: int
    realizado: bool

class CierreDiaCreate(BaseModel):
    usuario_id: int
    fecha: date
    registros_actividades: List[RegistroHabitoItem]
    texto_diario: str


# ==========================================
# ENDPOINTS / RUTAS DE LA API
# ==========================================

@app.get("/")
def home():
    return {"mensaje": "¡Backend de Hábitos y Diario funcionando correctamente!"}


# 1. Crear un Usuario
@app.post("/usuarios/", status_code=status.HTTP_201_CREATED)
def crear_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    db_usuario = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if db_usuario:
        raise HTTPException(status_code=400, detail="El email ya está registrado.")
    
    nuevo_usuario = Usuario(nombre=usuario.nombre, email=usuario.email)
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return {"mensaje": "Usuario creado con éxito", "usuario_id": nuevo_usuario.id}


# 2. Configurar el Inicio de Mes (Metas + Plantilla de Actividades)
@app.post("/meses/planificar", status_code=status.HTTP_201_CREATED)
def planificar_mes(plan: PlanificacionMesCreate, db: Session = Depends(get_db)):
    # Verificar si el usuario existe
    usuario = db.query(Usuario).filter(Usuario.id == plan.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    # Validar cantidad de metas y actividades
    if not (1 <= len(plan.metas) <= 3):
        raise HTTPException(status_code=400, detail="Debes ingresar entre 1 y 3 metas principales.")
    if not (5 <= len(plan.actividades) <= 10):
        raise HTTPException(status_code=400, detail="Debes ingresar entre 5 y 10 actividades diarias.")

    # Crear el mes planificado
    nuevo_mes = MesPlanificado(usuario_id=plan.usuario_id, anio=plan.anio, mes=plan.mes)
    db.add(nuevo_mes)
    
    try:
        db.commit()
        db.refresh(nuevo_mes)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Este mes ya fue planificado para este usuario.")

    # Guardar las metas
    for desc in plan.metas:
        meta = MetaMes(mes_planificado_id=nuevo_mes.id, descripcion=desc)
        db.add(meta)

    # Guardar la plantilla de actividades
    for act_nombre in plan.actividades:
        actividad = ActividadMes(mes_planificado_id=nuevo_mes.id, nombre_actividad=act_nombre)
        db.add(actividad)

    db.commit()
    return {"mensaje": "Planificación del mes guardada exitosamente", "mes_planificado_id": nuevo_mes.id}


# 3. Registrar el Cierre del Día (Checks de hábitos + Texto del diario)
@app.post("/dia/registrar", status_code=status.HTTP_200_OK)
def registrar_cierre_dia(datos: CierreDiaCreate, db: Session = Depends(get_db)):
    # Buscar el mes correspondiente a la fecha enviada
    anio = datos.fecha.year
    mes = datos.fecha.month

    mes_planificado = db.query(MesPlanificado).filter(
        MesPlanificado.usuario_id == datos.usuario_id,
        MesPlanificado.anio == anio,
        MesPlanificado.mes == mes
    ).first()

    if not mes_planificado:
        raise HTTPException(status_code=404, detail="No existe una planificación para este mes.")

    # 1. Guardar o actualizar la Nota del Diario
    nota_existente = db.query(NotaDiario).filter(
        NotaDiario.mes_planificado_id == mes_planificado.id,
        NotaDiario.fecha == datos.fecha
    ).first()

    if nota_existente:
        nota_existente.texto_relevante = datos.texto_diario
    else:
        nueva_nota = NotaDiario(
            mes_planificado_id=mes_planificado.id,
            fecha=datos.fecha,
            texto_relevante=datos.texto_diario
        )
        db.add(nueva_nota)

    # 2. Guardar los Checks de Hábitos de hoy
    for habito in datos.registros_actividades:
        reg_existente = db.query(RegistroActividadDiario).filter(
            RegistroActividadDiario.actividad_mes_id == habito.actividad_mes_id,
            RegistroActividadDiario.fecha == datos.fecha
        ).first()

        if reg_existente:
            reg_existente.realizado = habito.realizado
        else:
            nuevo_reg = RegistroActividadDiario(
                actividad_mes_id=habito.actividad_mes_id,
                fecha=datos.fecha,
                realizado=habito.realizado
            )
            db.add(nuevo_reg)

    db.commit()
    return {"status": "exitoso", "mensaje": "Cierre del día guardado correctamente."}

#AQ.Ab8RN6LqyjbX9uoUTZsG7HcYv5CfJaWTfMD-K7ZRCzvJLuv4iw

# Inicializar el cliente de Gemini (busca automáticamente la variable de entorno GEMINI_API_KEY)
# O bien puedes pasar tu clave directamente: client = genai.Client(api_key="TU_API_KEY_AQUÍ")
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LqyjbX9uoUTZsG7HcYv5CfJaWTfMD-K7ZRCzvJLuv4iw"))

# ==========================================
# ENDPOINT DE INTELIGENCIA ARTIFICIAL
# ==========================================

@app.get("/ia/motivacion-diaria/{usuario_id}")
def generar_motivacion_diaria(
    usuario_id: int, 
    fecha_consulta: date = date.today(), 
    db: Session = Depends(get_db)
):
    # 1. Obtener el usuario
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # 2. Buscar la planificación del mes según la fecha
    mes_planificado = db.query(MesPlanificado).filter(
        MesPlanificado.usuario_id == usuario_id,
        MesPlanificado.anio == fecha_consulta.year,
        MesPlanificado.mes == fecha_consulta.month
    ).first()

    if not mes_planificado:
        raise HTTPException(status_code=404, detail="No se encontró planificación para este mes.")

    # 3. Extraer las metas generales del mes
    metas_lista = [m.descripcion for m in mes_planificado.metas]
    metas_texto = ", ".join(metas_lista) if metas_lista else "Sin metas registradas."

    # 4. Extraer la nota del diario de la fecha indicada
    nota = db.query(NotaDiario).filter(
        NotaDiario.mes_planificado_id == mes_planificado.id,
        NotaDiario.fecha == fecha_consulta
    ).first()
    diario_texto = nota.texto_relevante if nota else "Hoy no escribió detalles en el diario."

    # 5. Calcular el porcentaje de cumplimiento de hábitos del día
    actividades = mes_planificado.actividades
    total_actividades = len(actividades)
    completadas = 0

    if total_actividades > 0:
        for act in actividades:
            reg = db.query(RegistroActividadDiario).filter(
                RegistroActividadDiario.actividad_mes_id == act.id,
                RegistroActividadDiario.fecha == fecha_consulta,
                RegistroActividadDiario.realizado == True
            ).first()
            if reg:
                completadas += 1

    porcentaje = int((completadas / total_actividades) * 100) if total_actividades > 0 else 0

    # 6. Diseñar el Prompt para la IA
    prompt = f"""
    Eres un coach personal y mentor empático. Tu trabajo es dar una frase motivacional diaria y personalizada.
    
    Información del usuario:
    - Nombre: {usuario.nombre}
    - Metas de este mes: {metas_texto}
    - Progreso de hábitos hoy: Completó {completadas} de {total_actividades} actividades ({porcentaje}% de cumplimiento).
    - Lo que escribió en su diario hoy: "{diario_texto}"
    
    Instrucciones:
    1. Escribe un mensaje directo para {usuario.nombre} de máximo 2 o 3 oraciones.
    2. Haz referencia sutil a su diario o al cumplimiento de sus hábitos hoy.
    3. Mantén un tono empático, realista y alentador (no tópicamente cursi).
    """

    # 7. Consultar a Gemini usando la versión ligera y rápida (gemini-2.5-flash)
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        mensaje_ia = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la IA: {str(e)}")

    # 8. Retornar la respuesta estructurada
    return {
        "usuario": usuario.nombre,
        "fecha": fecha_consulta,
        "cumplimiento_porcentaje": porcentaje,
        "mensaje_motivacional": mensaje_ia
    }


# ==========================================
# ENDPOINTS ADICIONALES PARA EL FRONTEND
# ==========================================

# Listar todos los usuarios (para el selector del frontend)
@app.get("/usuarios/")
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).all()
    return [{"id": u.id, "nombre": u.nombre, "email": u.email} for u in usuarios]


# Obtener la planificación de un mes específico (metas + actividades)
@app.get("/meses/{usuario_id}/{anio}/{mes}")
def obtener_mes(usuario_id: int, anio: int, mes: int, db: Session = Depends(get_db)):
    plan = db.query(MesPlanificado).filter(
        MesPlanificado.usuario_id == usuario_id,
        MesPlanificado.anio == anio,
        MesPlanificado.mes == mes
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="No hay planificación para este mes.")

    return {
        "id": plan.id,
        "anio": plan.anio,
        "mes": plan.mes,
        "metas": [{"id": m.id, "descripcion": m.descripcion} for m in plan.metas],
        "actividades": [{"id": a.id, "nombre_actividad": a.nombre_actividad} for a in plan.actividades],
    }


# Obtener registros del día (para precargar checkboxes y nota al abrir el diario)
@app.get("/dia/registros")
def obtener_registros_dia(usuario_id: int, fecha: date, db: Session = Depends(get_db)):
    anio = fecha.year
    mes  = fecha.month

    plan = db.query(MesPlanificado).filter(
        MesPlanificado.usuario_id == usuario_id,
        MesPlanificado.anio == anio,
        MesPlanificado.mes == mes
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="No hay planificación para este mes.")

    # Registros de actividades del día
    registros = []
    for act in plan.actividades:
        reg = db.query(RegistroActividadDiario).filter(
            RegistroActividadDiario.actividad_mes_id == act.id,
            RegistroActividadDiario.fecha == fecha
        ).first()
        registros.append({
            "actividad_mes_id": act.id,
            "nombre": act.nombre_actividad,
            "realizado": reg.realizado if reg else False
        })

    # Nota del diario del día
    nota = db.query(NotaDiario).filter(
        NotaDiario.mes_planificado_id == plan.id,
        NotaDiario.fecha == fecha
    ).first()

    return {
        "registros": registros,
        "nota_diario": nota.texto_relevante if nota else ""
    }
