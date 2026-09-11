import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# 1. Configuración de la base de datos SQLite local
DATABASE_URL = "sqlite:///./habitos_diario.db"

# connect_args={"check_same_thread": False} es necesario solo para SQLite en FastAPI
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ==========================================
# DEFINICIÓN DE MODELOS (TABLAS SQL)
# ==========================================

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    fecha_registro = Column(DateTime, default=datetime.datetime.utcnow)

    # Relaciones
    meses_planificados = relationship("MesPlanificado", back_populates="usuario", cascade="all, delete-orphan")


class MesPlanificado(Base):
    __tablename__ = "meses_planificados"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    anio = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('usuario_id', 'anio', 'mes', name='_usuario_mes_unico'),
    )

    # Relaciones
    usuario = relationship("Usuario", back_populates="meses_planificados")
    metas = relationship("MetaMes", back_populates="mes_planificado", cascade="all, delete-orphan")
    actividades = relationship("ActividadMes", back_populates="mes_planificado", cascade="all, delete-orphan")
    notas_diario = relationship("NotaDiario", back_populates="mes_planificado", cascade="all, delete-orphan")


class MetaMes(Base):
    __tablename__ = "metas_mes"

    id = Column(Integer, primary_key=True, index=True)
    mes_planificado_id = Column(Integer, ForeignKey("meses_planificados.id"), nullable=False)
    descripcion = Column(String, nullable=False)

    mes_planificado = relationship("MesPlanificado", back_populates="metas")


class ActividadMes(Base):
    __tablename__ = "actividades_mes"

    id = Column(Integer, primary_key=True, index=True)
    mes_planificado_id = Column(Integer, ForeignKey("meses_planificados.id"), nullable=False)
    nombre_actividad = Column(String, nullable=False)

    mes_planificado = relationship("MesPlanificado", back_populates="actividades")
    registros_diarios = relationship("RegistroActividadDiario", back_populates="actividad_mes", cascade="all, delete-orphan")


class RegistroActividadDiario(Base):
    __tablename__ = "registro_actividades_diario"

    id = Column(Integer, primary_key=True, index=True)
    actividad_mes_id = Column(Integer, ForeignKey("actividades_mes.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    realizado = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint('actividad_mes_id', 'fecha', name='_actividad_fecha_unica'),
    )

    actividad_mes = relationship("ActividadMes", back_populates="registros_diarios")


class NotaDiario(Base):
    __tablename__ = "notas_diario"

    id = Column(Integer, primary_key=True, index=True)
    mes_planificado_id = Column(Integer, ForeignKey("meses_planificados.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    texto_relevante = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('mes_planificado_id', 'fecha', name='_mes_fecha_nota_unica'),
    )

    mes_planificado = relationship("MesPlanificado", back_populates="notas_diario")


# ==========================================
# FUNCIÓN DE INICIALIZACIÓN
# ==========================================

def init_db():
    """Crea todas las tablas en la base de datos SQLite si no existen."""
    Base.metadata.create_all(bind=engine)
    print("¡Base de datos SQLite inicializada correctamente!")

if __name__ == "__main__":
    init_db()