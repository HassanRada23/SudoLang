# SudoLang - Proyecto N.1: analizador lexico, tabla de simbolos y manejador de errores
# Lenguajes Formales, Automatas y Compiladores - UTP

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

    def mostrar(self):
        print("\n" + "=" * 62 + "\nTABLA DE SIMBOLOS\n" + "=" * 62)
        print(f"{'Pos':<5}{'Lexema':<20}{'Token':<13}{'Tipo':<10}{'Linea'}")
        print("-" * 62)
        for pos, cubeta in enumerate(self.cubetas):
            for s in cubeta:
                print(f"{pos:<5}{s['lexema']:<20}{s['token']:<13}{s['tipo']:<10}{s['linea']}")


# ---------- MANEJADOR DE ERRORES ----------
class ManejadorErrores:
    def __init__(self):
        self.errores = []

    def reportar(self, linea, tipo, mensaje):
        self.errores.append((linea, tipo, mensaje))
        print(f"   [ERROR {tipo}] {mensaje}")       # se informa durante la evaluacion

    def mostrar(self):
        print("\n" + "=" * 62 + f"\nRESUMEN DE ERRORES ({len(self.errores)})\n" + "=" * 62)
        for linea, tipo, mensaje in self.errores:
            print(f"Linea {linea:<3} {tipo:<11} {mensaje}")


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


def analizar_semantica(tokens, n, tabla, errores):
    """Usa la tabla de simbolos: variables no declaradas o declaradas dos veces."""
    ok = True
    declara = tokens[0][0] == "TIPO"
    for k, (token, lexema) in enumerate(tokens):
        if token == "ID" and not (declara and k == 1) and tabla.buscar(lexema)["tipo"] == "-":
            errores.reportar(n, "SEMANTICO", f"variable '{lexema}' no declarada")
            ok = False
    if declara:
        simbolo = tabla.buscar(tokens[1][1])
        if simbolo["tipo"] != "-":
            errores.reportar(n, "SEMANTICO", f"variable '{simbolo['lexema']}' ya fue declarada")
            ok = False
        else:
            simbolo["tipo"] = tokens[0][1]        # se registra el tipo de la variable
    return ok


# ---------- PROGRAMA PRINCIPAL ----------
def main():
    tabla, errores = TablaSimbolos(), ManejadorErrores()
    for palabra, token in RESERVADAS.items():     # palabras reservadas precargadas
        tabla.instalar(palabra, token, "-", 0)

    print("=" * 62 + "\nSUDOLANG - Analizador lexico\n" + "=" * 62)
    while True:
        try:
            archivo = open(input("Archivo de entrada: ").strip(), encoding="utf-8")
            break
        except OSError:
            print("No se pudo abrir el archivo, intente de nuevo.")

    validas = total = 0
    for n, linea in enumerate(archivo, 1):
        cadena = linea.strip()
        if not cadena or cadena.startswith("#"):  # lineas vacias y comentarios
            continue
        total += 1
        print(f"\nLinea {n}: {cadena}")
        tokens, ok = analizar_lexico(cadena, n, tabla, errores)
        print("   Tokens:", " ".join(f"[{t} {l}]" for t, l in tokens))
        ok = ok and analizar_sintaxis(tokens, n, errores) and analizar_semantica(tokens, n, tabla, errores)
        print("   Resultado:", "VALIDA" if ok else "INVALIDA")
        validas += ok
    archivo.close()
    print(f"\nCadenas evaluadas: {total} | validas: {validas} | invalidas: {total - validas}")

    while True:
        opcion = input("\n1) Tabla de simbolos  2) Resumen de errores  3) Salir\nOpcion: ").strip()
        if opcion == "1": tabla.mostrar()
        elif opcion == "2": errores.mostrar()
        elif opcion == "3": break
        else: print("Opcion no valida.")


if __name__ == "__main__":
    main()
