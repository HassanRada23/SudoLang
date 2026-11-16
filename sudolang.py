# SudoLang - Proyecto N.1: analizador lexico, tabla de simbolos y manejador de errores
# Lenguajes Formales, Automatas y Compiladores - UTP
import tkinter as tk
from tkinter import ttk, filedialog

# ---------- DEFINICION DEL LENGUAJE ----------
RESERVADAS = {"entero": "TIPO", "decimal": "TIPO", "texto": "TIPO", "mostrar": "MOSTRAR"}

# AFD lexico: reconoce los tokens caracter por caracter (estado -> {clase: estado siguiente})
AFD_LEX = {
    "q0": {"L": "q1", "D": "q2", "C": "q5", "O": "q7", "I": "q8", "F": "q9"},
    "q1": {"L": "q1", "D": "q1"},                    # identificador
    "q2": {"D": "q2", "P": "q3"},                    # numero entero
    "q3": {"D": "q4"},                               # entero seguido de punto
    "q4": {"D": "q4"},                               # numero decimal
    "q5": {c: "q5" for c in "LDPOIFEX"} | {"C": "q6"},  # dentro de una cadena
    "q6": {}, "q7": {}, "q8": {}, "q9": {},          # cadena, operador, =, ;
}
FINALES = {"q1": "ID", "q2": "ENTERO", "q4": "DECIMAL", "q6": "CADENA",
           "q7": "OPERADOR", "q8": "ASIGNACION", "q9": "PUNTO_COMA"}

# AFD sintactico: valida el orden de los tokens de una sentencia
AFD_SIN = {
    "q0": {"TIPO": "q1", "ID": "q2", "MOSTRAR": "q3"},
    "q1": {"ID": "q2"},
    "q2": {"ASIGNACION": "q3"},
    "q3": {"ID": "q4", "ENTERO": "q4", "DECIMAL": "q4", "CADENA": "q4"},
    "q4": {"OPERADOR": "q3", "PUNTO_COMA": "q5"},
    "q5": {},                                        # estado final
}
ESPERA = {"q0": "un tipo, un identificador o 'mostrar'", "q1": "un identificador",
          "q2": "'='", "q3": "un operando (identificador, numero o texto)",
          "q4": "un operador o ';'", "q5": "el fin de la sentencia"}
TIPO_DE = {"ENTERO": "entero", "DECIMAL": "decimal", "CADENA": "texto"}

# Reglas de tipos: (tipo de la variable, tipo del valor) que se pueden asignar.
# Un entero cabe en un decimal; al reves se perderian los decimales.
COMPATIBLES = {("entero", "entero"), ("decimal", "decimal"),
               ("decimal", "entero"), ("texto", "texto")}


def clase(c):
    """Clasifica un caracter en un simbolo del alfabeto del AFD lexico."""
    if c.isalpha() or c == "_": return "L"   # letra
    if c.isdigit(): return "D"               # digito
    if c == ".": return "P"                  # punto
    if c == '"': return "C"                  # comilla
    if c in "+-*/": return "O"               # operador
    if c == "=": return "I"                  # igual
    if c == ";": return "F"                  # fin de sentencia
    if c in " \t": return "E"                # espacio
    return "X"                               # cualquier otro simbolo


# ---------- TABLA DE SIMBOLOS (HASH) ----------
class TablaSimbolos:
    def __init__(self, tam=31):
        self.tam = tam
        self.cubetas = [[] for _ in range(tam)]   # colisiones por encadenamiento

    def hash(self, lexema):
        """Suma de (codigo ASCII * posicion) modulo el tamano de la tabla."""
        return sum(ord(c) * (i + 1) for i, c in enumerate(lexema)) % self.tam

    def buscar(self, lexema):
        for simbolo in self.cubetas[self.hash(lexema)]:
            if simbolo["lexema"] == lexema:
                return simbolo
        return None

    def instalar(self, lexema, token, tipo, linea):
        if not self.buscar(lexema):               # no se repiten lexemas
            self.cubetas[self.hash(lexema)].append(
                {"lexema": lexema, "token": token, "tipo": tipo, "linea": linea})

    def filas(self):
        """Devuelve el contenido como filas (posicion, lexema, token, tipo, linea)."""
        return [(pos, s["lexema"], s["token"], s["tipo"], s["linea"])
                for pos, cubeta in enumerate(self.cubetas) for s in cubeta]


# ---------- MANEJADOR DE ERRORES (INTERFAZ DE USUARIO) ----------
class ManejadorErrores:
    """Ventana que muestra la evaluacion y los errores en el momento en que ocurren."""

    def __init__(self, tabla):
        self.errores, self.tabla = [], tabla
        self.ventana = tk.Tk()
        self.ventana.title("SudoLang - Manejador de errores")
        self.salida = tk.Text(self.ventana, width=100, height=18)   # evaluacion paso a paso
        self.salida.tag_config("error", foreground="red")
        self.salida.tag_config("valida", foreground="green")
        self.salida.pack(fill="both", expand=True)
        self.lista = self.crear_lista(self.ventana, ("Linea", "Tipo", "Mensaje"))
        self.boton = tk.Button(self.ventana, text="Ver tabla de simbolos",
                               state="disabled", command=self.mostrar_tabla)
        self.boton.pack(pady=5)

    def crear_lista(self, padre, columnas):
        lista = ttk.Treeview(padre, columns=columnas, show="headings", height=8)
        for c in columnas:
            lista.heading(c, text=c)
        lista.pack(fill="both", expand=True)
        return lista

    def escribir(self, texto, etiqueta=None):
        self.salida.insert("end", texto + "\n", etiqueta)
        self.salida.see("end")
        self.ventana.update()                     # refresca la ventana durante la evaluacion

    def reportar(self, linea, tipo, mensaje):
        self.errores.append((linea, tipo, mensaje))
        self.lista.insert("", "end", values=(linea, tipo, mensaje))
        self.escribir(f"   [ERROR {tipo}] {mensaje}", "error")

    def mostrar_tabla(self):
        ventana = tk.Toplevel(self.ventana)
        ventana.title("Tabla de simbolos")
        lista = self.crear_lista(ventana, ("Pos", "Lexema", "Token", "Tipo", "Linea"))
        for fila in self.tabla.filas():
            lista.insert("", "end", values=fila)


# ---------- ANALISIS ----------
def analizar_lexico(cadena, n, tabla, errores):
    """Recorre la cadena con el AFD lexico y devuelve (tokens, sin_errores)."""
    tokens, ok, i = [], True, 0
    while i < len(cadena):
        if clase(cadena[i]) == "E":               # los espacios se ignoran
            i += 1
            continue
        estado, j = "q0", i
        while j < len(cadena) and clase(cadena[j]) in AFD_LEX[estado]:
            estado = AFD_LEX[estado][clase(cadena[j])]
            j += 1
        lexema = cadena[i:j]
        if estado in FINALES:
            token = RESERVADAS.get(lexema, FINALES[estado])
            tokens.append((token, lexema))
            if token in ("ID", "ENTERO", "DECIMAL", "CADENA"):
                tabla.instalar(lexema, token, TIPO_DE.get(token, "-"), n)
        else:
            ok = False
            if estado == "q0":
                j = i + 1                         # se salta el simbolo invalido
                errores.reportar(n, "LEXICO", f"simbolo '{cadena[i]}' no reconocido (columna {i + 1})")
            elif estado == "q3":
                errores.reportar(n, "LEXICO", f"numero decimal incompleto '{lexema}' (columna {i + 1})")
            else:
                errores.reportar(n, "LEXICO", f"texto sin cerrar {lexema} (columna {i + 1})")
        i = j
    return tokens, ok


def analizar_sintaxis(tokens, n, errores):
    """Recorre los tokens con el AFD sintactico; es valida si termina en q5."""
    estado = "q0"
    for token, lexema in tokens:
        if token not in AFD_SIN[estado]:
            errores.reportar(n, "SINTACTICO", f"'{lexema}' inesperado, se esperaba {ESPERA[estado]}")
            return False
        estado = AFD_SIN[estado][token]
    if estado != "q5":
        errores.reportar(n, "SINTACTICO", f"sentencia incompleta, se esperaba {ESPERA[estado]}")
        return False
    return True


def tipo_expresion(expresion, n, tabla, errores):
    """Calcula el tipo de una expresion con la tabla de simbolos; None si los tipos no se mezclan."""
    tipos = {tabla.buscar(lexema)["tipo"] if token == "ID" else TIPO_DE[token]
             for token, lexema in expresion if token != "OPERADOR"}
    operadores = {lexema for token, lexema in expresion if token == "OPERADOR"}
    if "texto" in tipos:
        if len(tipos) > 1:
            errores.reportar(n, "SEMANTICO", "no se puede operar texto con numeros")
            return None
        if operadores - {"+"}:                    # con texto solo se permite unir con +
            errores.reportar(n, "SEMANTICO",
                             f"el operador '{min(operadores - {'+'})}' no se puede usar con texto")
            return None
        return "texto"
    return "decimal" if "decimal" in tipos else "entero"


def analizar_semantica(tokens, n, tabla, errores):
    """Usa la tabla de simbolos: variables no declaradas, declaradas dos veces y tipos incompatibles."""
    ok = True
    declara = tokens[0][0] == "TIPO"
    for k, (token, lexema) in enumerate(tokens):
        if token == "ID" and not (declara and k == 1) and tabla.buscar(lexema)["tipo"] == "-":
            errores.reportar(n, "SEMANTICO", f"variable '{lexema}' no declarada")
            ok = False
    variable = tipo_variable = None               # a quien se le asigna el valor
    if declara:
        variable, tipo_variable = tokens[1][1], tokens[0][1]
        simbolo = tabla.buscar(variable)
        if simbolo["tipo"] != "-":
            errores.reportar(n, "SEMANTICO", f"variable '{variable}' ya fue declarada")
            ok = False
        else:
            simbolo["tipo"] = tipo_variable       # se registra el tipo de la variable
    elif tokens[0][0] == "ID":
        variable, tipo_variable = tokens[0][1], tabla.buscar(tokens[0][1])["tipo"]
    if ok:                                        # solo se revisan tipos si todo esta declarado
        inicio = next(k for k, (t, _) in enumerate(tokens) if t in ("ASIGNACION", "MOSTRAR")) + 1
        tipo_valor = tipo_expresion(tokens[inicio:-1], n, tabla, errores)
        if tipo_valor is None:
            ok = False
        elif variable and (tipo_variable, tipo_valor) not in COMPATIBLES:
            errores.reportar(n, "SEMANTICO", f"no se puede guardar un valor {tipo_valor} "
                                             f"en '{variable}', que es de tipo {tipo_variable}")
            ok = False
    return ok


# ---------- PROGRAMA PRINCIPAL ----------
def leer_archivo(ruta):
    """Devuelve las lineas del archivo, o None si no se puede abrir.
    Acepta UTF-8 con o sin BOM y, si no lo es, ANSI de Windows (acentos y ñ)."""
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(ruta, encoding=codificacion) as archivo:
                return archivo.readlines()
        except UnicodeDecodeError:
            continue                              # se prueba la siguiente codificacion
        except OSError:
            return None
    return None


def main():
    tabla = TablaSimbolos()
    errores = ManejadorErrores(tabla)
    for palabra, token in RESERVADAS.items():     # palabras reservadas precargadas
        tabla.instalar(palabra, token, "-", 0)

    ruta = filedialog.askopenfilename(title="Seleccione el archivo de entrada")
    if not ruta:                                  # el usuario cancelo
        return

    lineas = leer_archivo(ruta)
    if lineas is None:                            # no se pudo abrir: se avisa en la ventana
        errores.escribir(f"No se pudo abrir el archivo {ruta}", "error")
        errores.ventana.mainloop()
        return

    validas = total = 0
    for n, linea in enumerate(lineas, 1):
        cadena = linea.strip()
        if not cadena or cadena.startswith("#"):  # lineas vacias y comentarios
            continue
        total += 1
        errores.escribir(f"\nLinea {n}: {cadena}")
        tokens, ok = analizar_lexico(cadena, n, tabla, errores)
        errores.escribir("   Tokens: " + " ".join(f"[{t} {l}]" for t, l in tokens))
        ok = ok and analizar_sintaxis(tokens, n, errores) and analizar_semantica(tokens, n, tabla, errores)
        errores.escribir("   Resultado: " + ("VALIDA" if ok else "INVALIDA"), "valida" if ok else "error")
        validas += ok
        errores.ventana.after(300)                # pausa para ver la evaluacion paso a paso

    errores.escribir(f"\nCadenas evaluadas: {total} | validas: {validas} | invalidas: {total - validas}")
    errores.boton.config(state="normal")          # al final se habilita la tabla de simbolos
    errores.ventana.mainloop()


if __name__ == "__main__":
    main()