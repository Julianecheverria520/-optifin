from datetime import date
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints, model_validator

# El usuario de cada operación sale del token de sesión (backend/seguridad.py), nunca del cuerpo de la petición.

# Texto obligatorio: se recortan espacios y no puede quedar vacío
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
MontoPositivo = Annotated[float, Field(gt=0)]

TipoCategoria = Literal["Gasto", "Ingreso"]
TipoMovimiento = Literal["Gasto", "Ingreso", "Traslado"]
TipoCuenta = Literal["Débito", "Billetera Digital", "Efectivo", "Crédito"]
TipoPlan = Literal["Gasto Fijo", "Ingreso Fijo", "Gasto Variable (Presupuesto)"]
SiNo = Literal["Sí", "No"]
TipoDeuda = Literal["Me debe", "Le debo"]


class Cuenta(BaseModel):
    nombre_cuenta: Texto
    tipo_cuenta: TipoCuenta
    saldo_inicial: float  # Puede ser negativo (p. ej. deuda de tarjeta de crédito)


class Categoria(BaseModel):
    nombre_categoria: Texto
    tipo_movimiento: TipoCategoria


class Subcategoria(BaseModel):
    id_categoria: int
    nombre_subcategoria: Texto


class PlanificacionUpdate(BaseModel):
    # El estado (pagado/pendiente/vencido) ya no se guarda: se calcula cada mes a partir de los movimientos
    tipo: TipoPlan
    nombre_concepto: Texto
    monto: MontoPositivo
    dia_mes: Optional[Annotated[int, Field(ge=1, le=31)]] = None
    id_subcategoria: int
    # Vigencia por meses: desde el mes de fecha_inicio hasta el de fecha_fin (None = indefinido)
    fecha_inicio: date
    fecha_fin: Optional[date] = None
    # Solo topes presupuestales: "Quincenal" = el monto es por quincena (1-15 y 16-fin de mes)
    periodicidad: Literal["Mensual", "Quincenal"] = "Mensual"

    @model_validator(mode="after")
    def normalizar(self):
        # Un tope presupuestal no tiene día de pago; los fijos siempre son mensuales
        if self.tipo == "Gasto Variable (Presupuesto)":
            self.dia_mes = None
        else:
            self.periodicidad = "Mensual"
        # La vigencia es por mes: se guarda siempre el día 1
        self.fecha_inicio = self.fecha_inicio.replace(day=1)
        if self.fecha_fin is not None:
            self.fecha_fin = self.fecha_fin.replace(day=1)
            if self.fecha_fin < self.fecha_inicio:
                raise ValueError("El mes final no puede ser anterior al mes de inicio")
        return self


class Planificacion(PlanificacionUpdate):
    activo: SiNo = "Sí"


class ActivoUpdate(BaseModel):
    activo: SiNo


class AjusteMes(BaseModel):
    """Monto de un concepto solo para un mes; la plantilla de planificación no cambia."""
    monto: MontoPositivo


class Participante(BaseModel):
    """Persona que debe parte de un gasto compartido (usuario de OptiFin o no)."""
    persona: Texto
    monto: MontoPositivo


class Transaccion(BaseModel):
    fecha: date
    tipo_movimiento: TipoMovimiento
    id_subcategoria: Optional[int] = None
    id_cuenta_origen: Optional[int] = None
    id_cuenta_destino: Optional[int] = None
    monto: MontoPositivo
    descripcion: Optional[str] = ""
    # Gasto compartido: cada participante queda como una deuda "Me debe" ligada a esta transacción.
    # Solo se usa al crear; para cambiar las partes se editan/eliminan las deudas.
    compartido: list[Participante] = []
    # Gasto que pagó otra persona por mí: el monto es mi parte, no sale de ninguna cuenta
    # y queda una deuda "Le debo" con esa persona.
    pagado_por: Optional[Texto] = None

    @model_validator(mode="after")
    def validar_compartido(self):
        if not self.compartido:
            return self
        if self.tipo_movimiento != "Gasto":
            raise ValueError("Solo un gasto puede ser compartido")
        if sum(p.monto for p in self.compartido) > self.monto + 0.005:
            raise ValueError("Lo que te deben no puede superar el total del gasto")
        nombres = [p.persona.casefold() for p in self.compartido]
        if len(nombres) != len(set(nombres)):
            raise ValueError("Hay personas repetidas en el gasto compartido")
        return self

    @model_validator(mode="after")
    def validar_segun_tipo(self):
        if self.pagado_por is not None:
            if self.tipo_movimiento != "Gasto":
                raise ValueError("Solo un gasto puede haberlo pagado otra persona")
            if self.compartido:
                raise ValueError("Un gasto que pagó otra persona no puede ser además compartido")
            if self.id_subcategoria is None:
                raise ValueError("Un gasto necesita una subcategoría")
            self.id_cuenta_origen = None  # el dinero no salió de mis cuentas
            self.id_cuenta_destino = None
            return self

        if self.tipo_movimiento == "Gasto":
            if self.id_cuenta_origen is None:
                raise ValueError("Un gasto necesita una cuenta de origen")
            if self.id_subcategoria is None:
                raise ValueError("Un gasto necesita una subcategoría")
            self.id_cuenta_destino = None
        elif self.tipo_movimiento == "Ingreso":
            if self.id_cuenta_destino is None:
                raise ValueError("Un ingreso necesita una cuenta de destino")
            if self.id_subcategoria is None:
                raise ValueError("Un ingreso necesita una subcategoría")
            self.id_cuenta_origen = None
        else:  # Traslado
            if self.id_cuenta_origen is None or self.id_cuenta_destino is None:
                raise ValueError("Un traslado necesita cuenta de origen y de destino")
            if self.id_cuenta_origen == self.id_cuenta_destino:
                raise ValueError("No puedes trasladar dinero a la misma cuenta")
            self.id_subcategoria = None
        return self


class Deuda(BaseModel):
    # El estado (Pendiente/Parcial/Pagada) se calcula a partir de los abonos
    persona: Texto
    tipo_deuda: TipoDeuda
    monto: MontoPositivo
    fecha_creacion: date
    # Cuenta de donde salió (presté) o a donde entró (me prestaron) el dinero; None = deuda previa sin movimiento
    id_cuenta: Optional[int] = None


class LiquidacionNueva(BaseModel):
    """Propuesta de cruce de cuentas con una persona: se compensa lo que me debe con lo que le debo."""
    persona: Texto



class Abono(BaseModel):
    fecha: date
    monto: MontoPositivo
    # Cuenta donde entra (me pagan) o de donde sale (yo pago) el abono; None = sin movimiento de cuenta
    id_cuenta: Optional[int] = None
    descripcion: Optional[str] = ""
