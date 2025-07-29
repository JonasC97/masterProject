


# ----------------------------------------------
# build_zod_from_template.py
# ----------------------------------------------
from __future__ import annotations
from collections import defaultdict
import re
from typing import List, Dict, Any, DefaultDict

import json
import os
import string
import warnings




_PRIM = {
    "string": "z.string()",
    "number": "z.number()",
    "bool":   "z.boolean()",
    "null":   "z.null()",           # <- wichtig
}

_BOOL_STR = {"true": True, "false": False}

_emitted: set[str] = set()


# ---------- Hilfsfunktionen ------------------------------------------------
def _pascal(name: str) -> str:
    return re.sub(r'[^0-9a-zA-Z]+', ' ', name).title().replace(' ', '')+"Schema"

def _fix_literal(dt: str, fv: Any) -> str:
    # Empty Array
    if isinstance(fv, list) and len(fv) == 0:
        # unabhängig vom dataType → leeres String-Array
        return "z.array(z.string()).length(0)"
    # Null
    if dt == "null" or (isinstance(fv, str) and fv.lower() == "null"):
        return "z.null()"
    # Bool
    if dt == "bool" or str(fv).lower() in _BOOL_STR:
        return f"z.literal({str(_BOOL_STR.get(str(fv).lower(), fv)).lower()})"
    # Number
    if dt == "number" and str(fv).replace('.', '', 1).isdigit():
        return f"z.literal({fv})"
    # String (auch leer)
    return f"z.literal({json.dumps(fv)})"


def _field_expr(prop: Dict[str, Any]) -> str:
    fv, dt = prop.get("fixValue"), prop["dataType"]
    if fv is not None:
        return _fix_literal(dt, fv)

    if prop.get("choices"):
        return f"z.enum({prop['choices']})"

    if "|" in dt:                                # unions
        return "z.union([" + ", ".join(_PRIM.get(d.strip(), "z.any()")
                                       for d in dt.split("|")) + "])"

    # length 0 arrays
    if dt == "objects" and not prop.get("objectProperties"):
        return "z.tuple([])"

    return _PRIM.get(dt, "z.any()")

def _schema_name(meta: dict[str, Any], fallback: str) -> str:
    """Nimmt schemaName, falls vorhanden, sonst fallback."""
    return meta.get("schemaName") or fallback

# ---------- Rekursiver Builder ---------------------------------------------
def _emit_schema(name: str,
                 props: List[Dict[str, Any]],
                 out: List[str]) -> str:
    
    if name in _emitted:             # ← Neu
        return name                  # einfach nur referenzieren
    _emitted.add(name)               # ← Neu

    lines = []

    if gptFineTuningJson["usingReasoningField"] is True:
        lines.append(f"  reasoningSteps: z.string().describe('Nutze dieses Feld für Reasoning. Insbesondere das Layouting und die Dimensionierung der einzelnen Shapes und anschließend der Dimensionierung des Gesamt-Template auf Basis aller Shapes kann hier sinnvollerweise geplant werden.'),")

    for p in props:
        if p.get("multipleTypes"):
            # für jede Variante ein eigenes Schema
            sub_names = []
            for t in p["types"]:
                sub_name = _schema_name(t, _pascal(t["name"]))
                sub_names.append(sub_name)
                _emit_schema(sub_name, t["objectProperties"], out)
            union_expr = f"z.union([{', '.join(sub_names)}])"
            lines.append(f"  {p['propertyName']}: z.array({union_expr}),")
        elif p["dataType"] == "objects" and p.get("objectProperties"):
            sub_name = _schema_name(p, _pascal(p["propertyName"]))
            _emit_schema(sub_name, p["objectProperties"], out)
            lines.append(f"  {p['propertyName']}: z.array({sub_name}),")
        else:
            expr = _field_expr(p)
            if p.get("isUuid"):
                if expr.endswith("()"):
                    expr = expr[:-2] + "().uuid()"
                else:
                    expr += ".uuid()"
            lines.append(f"  {p['propertyName']}: {expr},")


    if gptFineTuningJson["schemaValidationProperty"] is not None:
        already = any(p["propertyName"] == gptFineTuningJson["schemaValidationProperty"] for p in props)
        if not already:
            lines.append(f"  {gptFineTuningJson["schemaValidationProperty"]}: z.boolean(),")


    # 🟢 1. Letztes Komma entfernen
    if lines:
        lines[-1] = lines[-1].rstrip(",") 

    schema_code = f"const {name} = z.object({{\n" + "\n".join(lines) + "\n}).strict();"
    out.append(schema_code)
    return name


# ---------- öffentliche Hauptfunktion --------------------------------------
def build_zod_from_template(tpl_props: List[Dict[str, Any]],
                            root_name="TemplateSchema") -> str:
    out = ["-------- SCHEMATA --------"]
    _emit_schema(root_name, tpl_props, out)
    return "\n\n".join(out)


# print("Aktuelles Arbeitsverzeichnis:", os.getcwd())

# Gib den absoluten Pfad der JSON-Datei aus
# print("Pfad zur JSON-Datei:", os.path.abspath('GenericGPTFinetuningJSON.json'))

with open('C:/Users/jonas/Documents/Masterarbeit/GenericGPTFinetuningJSON.json','r', encoding="utf-8") as file:
    gptFineTuningJson = json.load(file)
    # print(gptFineTuningJson)


def generateGPTFinetuningText():
    text = ""
    text += getInitialExplanation()

    schemaDefinitions = None

    if gptFineTuningJson["usingStructuredOutput"] == True:
        additionalDataModelExplanations = getDataModelExplanationWithStructuredOutput()
        schemaDefinitions = getSchemaDefinitions()
        text += additionalDataModelExplanations
    else:
        text += getDataModelExplanation()

    text += getRecommendedSteps()
    text += getCustomAreaRules()
    text += getFinalRules()
    
    if len(text) > 10000:
        raise ValueError(f"Die erstellte Systemnachricht ist zu lang ({str(len(text))} Zeichen)  und überschreitet damit das Zeichenlimit, das der GPT Builder vorgibt (8000 Zeichen). Versuchen Sie durch Anpassen der Konfigurationsdatei Kürzungen vorzunehmen.")
    elif len(text) > 6000:
        warnings.warn("WARNUNG! Die erstellte Systemnachricht hat " + str(len(text)) + " Zeichen. Der GPT Builder erlaubt zwar bis zu 8000 Zeichen, aber Nutzererfahrungen zeigen, dass so lange Kontexte dazu neigen, dass einzelne Regeln nicht mehr so zuverlässig befolgt werden. Versuchen Sie durch Anpassen der Konfigurationsdatei Kürzungen vorzunehmen.")
    
    print(text)
    if schemaDefinitions:
        print(schemaDefinitions)

def getInitialExplanation():
    newInitialExplanation = gptFineTuningJson["mainGoal"] + "\n"

    if gptFineTuningJson["schemaValidationProperty"]:
        schemaValidationExplanator = ""
        if gptFineTuningJson["schemaValidationExplanator"]:
            schemaValidationExplanator = f"({gptFineTuningJson["schemaValidationExplanator"]}) "

        newInitialExplanation += "\n" + "Eine Themenverfehlung " + schemaValidationExplanator + "wird im Feld 'isValidSchema' festgehalten. Bei fehlerhaftem Prompt: false, ansonsten: true"

    initialExplanation = "Diese GPT generiert basierend auf einem Prompt ein " + gptFineTuningJson["format"] + ", das ein NodeTemplate für ein Überwachungs-/Monitoring-Softwareprodukt beschreibt. Dieses Dieses Template repräsentiert einen Domänenobjekttyp, von dem sich abgeleitete Nodes im Diagramm platzieren und mit Instanzen verknüpfen lassen.\n" \
    "\n##Prinzipien:\n" \
    "- Gibt stets wohlgeformtes, validierbares " + gptFineTuningJson["format"] + ". Der Output darf NUR aus diesem " + gptFineTuningJson["format"] + " bestehen! Einzige Ausnahme: Nutzer verfehlt Thema. Dann gib exakt 'false' zurück.\n" \
    "- Nutzt ein zentrales Datenmodell zur Sicherung von Konsistenz und Integration.\n"
    return newInitialExplanation #initialExplanation


def getDataModelExplanationNew():
    """
    Baut einen Markdown-String mit allen Zusatzregeln.
    """
    title = "\n## Template-Struktur:\nFeste Vorgaben (Template):\n"
    sections = _walk(gptFineTuningJson["templateProperties"])
    if not sections:                # nichts zu erklären
        return ""

    lines: list[str] = [title]
    # Pfade sortieren, Root zuerst, dann Sub-Pfad
    for path in sorted(sections.keys(), key=lambda p: p.count(".")):
        lines.append(f"### {path} ")

        lines.extend(sections[path])
        lines.append("")   # Leerzeile nach jeder Section
        # for bullet in sections[path]:
        #     lines.append(f"- {bullet}")
        # lines.append("")            # Leerzeile nach jeder Section
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hilfs-Helper: Roh-Zeilen aus _collect_rules in eine Einzeile kondensieren
# ---------------------------------------------------------------------------
def _flatten_rules(raw: List[str]) -> str:
    """
    Entfernt führende Spiegelstriche und Leerzeichen aus den von
    _collect_rules gelieferten Zeilen und fasst sie zu einem Satz zusammen.
    """
    cleaned = [ln.lstrip("- ").strip() for ln in raw if ln.strip()]
    return " ".join(cleaned)  # mehrere Absätze hintereinander

# ---------------------------------------------------------------------------
# Rekursive Traversierung für die kompakte Vollstruktur
# ---------------------------------------------------------------------------
def _walk_full(props: List[Dict[str, Any]], indent: int = 0) -> List[str]:
    """
    Baut eine hierarchische Liste:
       - name (type): Zusatz …
       - child …
          - subChild …
    """
    pad = "  " * indent
    out: List[str] = []

    for p in props:
        # Kopfzeile
        line = f"{pad}- {p['propertyName']} ({p['dataType']})"

        # --- Zusatzinfos zusammensetzen ----------------------------------
        extra: List[str] = []

    
        # 1) Fixwert
        if "fixValue" in p:
            fv_raw = p["fixValue"]          # kommt als String, Zahl oder bool

            # ------------- String-Entscheidung ---------------
            dt = p["dataType"]              # z. B. 'number', 'string | null'

            def _is_num_bool_null(value: str, dtype: str) -> bool:
                if any(tok in dtype for tok in ("number", "integer", "bool", "null")):
                    return True
                return value in ("true", "false", "null")

            if isinstance(fv_raw, str) and not _is_num_bool_null(fv_raw, dt):
                pretty = f'"{fv_raw}"'      # echte String-Literale in Quotes
            else:
                pretty = fv_raw             # Zahl, bool oder null → unverändert

            extra.append(str(pretty))

        # 2) Regeltexte aus description / customRules / generationRule
        if (raw := _collect_rules(p)):
            extra.append(_flatten_rules(raw))

            # 2b) Choices
        if p.get("choices"):
            joined = "', '".join(map(str, p["choices"]))
            extra.append(f"Muss einen der folgenden Werte annehmen (case-sensitive): '{joined}'")

        # 3) neue UUID-Regel
        if p.get("isUuid"):
            extra.append("gültige UUID")

        # ggf. weitere Meta-Felder (choices, fixValue etc.) hier analog

        # Extras anhängen, getrennt durch Semikolon
        if extra:
            line += f": {'; '.join(extra)}"

        out.append(line)

        # ----- objectProperties -----
        if p["dataType"] == "objects" and p.get("objectProperties"):
            out.extend(_walk_full(p["objectProperties"], indent + 1))

        # ----- multipleTypes -----
        if p.get("multipleTypes"):
            for t in p["types"]:
                out.append(f"{pad}  - [{t['name']}]")
                out.extend(_walk_full(t["objectProperties"], indent + 2))
    return out



def getDataModelExplanation():
    # propertyConcatenationString = ""
    # dataModelPropertyDetailExplanations = []

    templateStructureText = _walk_full(gptFineTuningJson["templateProperties"])

    if not templateStructureText:
        return ""
    
    return "\n".join(["\n## Template-Struktur:\nFeste Vorgaben (Template):\n"] + templateStructureText + [""])

    objectsProperties = []

    dataModelExplanation = "\n##Template-Struktur:\n" # Unterstützt folgende Top Level Attribute:: " + propertyConcatenationString + ".\n"
    dataModelExplanation += "Feste Vorgaben (Template):\n"


    # Iterate through all the Top Level Properties of the Template
    for property in gptFineTuningJson["templateProperties"]:
        # Gather all the Property Names in a concatenation string
        # propertyConcatenationString += property["propertyName"] + ", "

        propertyDetails = "- " + property["propertyName"] + "(" + property["dataType"] + ")"
        delimiterSet = False

        if "fixValue" in property:
            fixValue = property["fixValue"]
            if "fixValueTransformer" in property:
                match property["fixValueTransformer"]:
                    case "Stringify":
                        fixValue = '"' + fixValue + '"'
            propertyDetails += f": {fixValue}"
            delimiterSet = True
            # dataModelPropertyDetailExplanations.append("\t- `" + property["propertyName"] + "` wird **immer** auf `" + fixValue + "` gesetzt.\n")

        if "isUuid" in property and property["isUuid"] == True:
            prefix = getPrefix(delimiterSet)
            propertyDetails += prefix + "gültige UUID"
            delimiterSet = True

        if property["dataType"] == "objects":
            # Sammle alle Properties, die vom Typ 'objects' ist, denn durch diese muss später ebenfalls auf tieferer Ebene iteriert werden.
            objectsProperties.append(property)

        if "description" in property and property["description"] is not None:
            prefix = getPrefix(delimiterSet)            
            propertyDetails += prefix + property["description"]
            delimiterSet = True
            # dataModelPropertyDetailExplanations.append("\t- `" + property["propertyName"] + "` " +  property["description"] + "\n")

        if "generatedFromFile" in property:
            prefix = getPrefix(delimiterSet)            
            propertyDetails += prefix + "Mithilfe von " + property["generatedFromFile"] + " setzen."
            if "generationRule" in property:
                propertyDetails += property["generationRule"]
            delimiterSet = True

        # match property["dataType"]:
        #     case "objects":
        #         # Sammle alle Properties, die vom Typ 'objects' ist, denn durch diese muss später ebenfalls auf tieferer Ebene iteriert werden.
        #         objectsProperties.append(property)
        #     case "uuid":
        #         dataModelPropertyDetailExplanations.append("\t- `" + property["propertyName"] + "` muss eine gültige, global eindeutige UUID sein.\n")

        # if "dataTypeDependation" in property:
            # for dataType in property["dataType"]:
            #     if dataType["type"] == "colorString":
            #         suffix = " ein Farbwert in Hexcode sein"
            #     else:
            #         suffix = " ein " + dataType["value"] + " sein"

            #     if dataType["choices"]:
            #         choicesConcatentionString = ""
            #         for choice in dataType["choices"]:
            #             choicesConcatentionString += choice + ", "
            #         if len(choicesConcatentionString) > 0:
            #             choicesConcatentionString = choicesConcatentionString[:-2]

            #         suffix += " und einen der folgenden Werte annehmen: " + choicesConcatentionString

            #     dataModelPropertyDetailExplanations.append("\t- Falls `" + property["dataTypeDependation"] + '` **"' + dataType["value"] + '"** ist, muss ' + property["propertyName"] + suffix)
        
        if "customRules" in property:
            if len(property["customRules"]) == 1:
                prefix = getPrefix(delimiterSet)
                propertyDetails += prefix + property["customRules"][0]
                delimiterSet = True
            else:
                for customRule in property["customRules"]:
                    propertyDetails += "\n\t- " + customRule
                    # dataModelPropertyDetailExplanations.append("\t-" + customRule + "\n")

        dataModelExplanation += propertyDetails + "\n"


    # Remove last two characters to get rid of unnecessary last comma
    # propertyConcatenationString = propertyConcatenationString[:-2]
        
    # for dataModelPropertyDetailExplanation in dataModelPropertyDetailExplanations:
    #     dataModelExplanation += dataModelPropertyDetailExplanation

    for objectsProperty in objectsProperties:
        innerDataModelExplanation = getInnerDataModelExplanation(objectsProperty, "Template." + objectsProperty["propertyName"])
        dataModelExplanation += innerDataModelExplanation#"- **" + objectsProperty + "** befinden sich auf Top-Level-Ebene im Template und haben folgende Attribute:"


    return dataModelExplanation


# -------------------------------------------------------------------------
# 1) Regel-Sammler
# -------------------------------------------------------------------------
def _collect_rules(prop: Dict[str, Any]) -> List[str] | None:
    """
    Liefert eine Liste von Markdown-Zeilen OHNE führenden Spiegelstrich.
    • Für mehrere Regeln (>=2) wird eine mehrzeilige Liste zurückgegeben:
        ["", "- Regel 1", "- Regel 2", ...]
    • Für Einzeltext / Beschreibung nur eine Zeile.
    """
    # 1) Reihenfolge‐Priorität
    acc: List[str] = []
    if prop.get("description"):
        acc.append(str(prop["description"]))

    if cr := prop.get("customRules"):
        # Wenn mehrere customRules → mehrzeiliges Format
        if isinstance(cr, list):
            if len(cr) > 1:
                return [""] + cr          # << kein '- ' mehr
            acc.extend(cr)
        else:
            acc.append(str(cr))

    if prop.get("generationRule"):
        acc.append(str(prop["generationRule"]))

    return acc or None


# -------------------------------------------------------------------------
# 2) Tiefensuche – baut Pfad → Markdown-Zeilen
# -------------------------------------------------------------------------
def _walk(props: List[Dict[str, Any]],
          base_path: str = "Template") -> Dict[str, List[str]]:
    """
    Rekursive DFS über templateProperties.
    Rückgabe: { Abschnittspfad : [Markdown-Zeilen] }
    """
    out: DefaultDict[str, List[str]] = defaultdict(list)

    for p in props:
        # --- 1. Regeln einsammeln -----------------------------------------
        bullets = _collect_rules(p)
        if bullets:
            section = base_path           # z. B. "Template.nodeShapes"
            if bullets[0] == "":          # Mehrzeiler (customRules >= 2)
                out[section].append(f"- {p['propertyName']}:")
                out[section].extend(f"\t- {b}" for b in bullets[1:])
            else:                         # Einzeiler
                # joined = " ".join(bullets)
                # out[section].append(f"- {p['propertyName']}: {joined}")
                out[section].append(f"- {p['propertyName']}: {' '.join(bullets)}")


        # --- 2. Rekursion für objectProperties ----------------------------
        if p["dataType"] == "objects" and p.get("objectProperties"):
            sub_path = f"{base_path}.{p['propertyName']}"
            for k, v in _walk(p["objectProperties"], sub_path).items():
                out[k].extend(v)

        # --- 3. multipleTypes --------------------------------------------
        if p.get("multipleTypes"):
            sub_path = f"{base_path}.{p['propertyName']}"
            for t in p["types"]:
                for k, v in _walk(t["objectProperties"], sub_path).items():
                    out[k].extend(v)
    return out

def getDataModelExplanationWithStructuredOutput():
    """
    Baut einen Markdown-String mit allen Zusatzregeln.
    """
    title = "\n\n## Zusatzerklärungen zu einzelnen Properties"
    sections = _walk(gptFineTuningJson["templateProperties"])
    if not sections:                # nichts zu erklären
        return ""

    lines: list[str] = [title]
    # Pfade sortieren, Root zuerst, dann Sub-Pfad
    for path in sorted(sections.keys(), key=lambda p: p.count(".")):
        lines.append(f"### {path} ")

        lines.extend(sections[path])
        lines.append("")   # Leerzeile nach jeder Section
        # for bullet in sections[path]:
        #     lines.append(f"- {bullet}")
        # lines.append("")            # Leerzeile nach jeder Section
    return "\n".join(lines)

    objectsProperties = []

    dataModelExplanation = "\n## Zusatzerklärungen zu einzelnen Properties:\n" # Unterstützt folgende Top Level Attribute:: " + propertyConcatenationString + ".\n"
    zodSchemaDefinition = ""


    return dataModelExplanation


def getSchemaDefinitions():
    zod_code = build_zod_from_template(gptFineTuningJson["templateProperties"], "TemplateSchema")
    return zod_code


def getPrefix(delimiterSet):
    if delimiterSet:
        return "; "
    else:
        return ": "
    

def getInnerDataModelExplanation(propertyObject, propertyPath):
    # innerPropertyConcatenationString = ""
    # innerPropertyDetailExplanations = []
    objectsProperties = []

    innerDataModelExplanation = "\nFeste Vorgaben (" + propertyPath + "):\n"

    for innerProperty in propertyObject["objectProperties"]:
        # innerPropertyConcatenationString += innerProperty["propertyName"] + ", "
        innerPropertyDetails = "- " + innerProperty["propertyName"] + "(" + innerProperty["dataType"] + ")"
        delimiterSet = False

        if "fixValue" in innerProperty:
            fixValue = innerProperty["fixValue"]
            if "fixValueTransformer" in innerProperty:
                match innerProperty["fixValueTransformer"]:
                    case "Stringify":
                        fixValue = '"' + fixValue + '"'
            # innerPropertyDetailExplanations.append("\t- `" + innerProperty["propertyName"] + ": " + fixValue + "\n")
            innerPropertyDetails += ": " + fixValue
            delimiterSet = True


        if "isUuid" in innerProperty and innerProperty["isUuid"] == True:
            prefix = getPrefix(delimiterSet)
            innerPropertyDetails += prefix + "gültige UUID"
            delimiterSet = True

        if "choices" in innerProperty:
            prefix = getPrefix(delimiterSet)
            choicesConcatenationString = ""
            for choice in innerProperty["choices"]:
                choicesConcatenationString += '"' + choice + '", '
            choicesConcatenationString = choicesConcatenationString[:-2]

            innerPropertyDetails += prefix + "Nur " + choicesConcatenationString + " (case-sensitive)"
            delimiterSet = True


        if innerProperty["dataType"] == "objects":
            # Sammle alle Properties, die vom Typ 'objects' ist, denn durch diese muss später ebenfalls auf tieferer Ebene iteriert werden.
            objectsProperties.append(innerProperty)

        if "description" in innerProperty and innerProperty["description"] is not None:
            # innerPropertyDetailExplanations.append("\t- " + innerProperty["propertyName"] + ": " + innerProperty["description"] + "\n")
            prefix = getPrefix(delimiterSet)            
            innerPropertyDetails += prefix + innerProperty["description"]

        if "customRules" in innerProperty:
            if len(innerProperty["customRules"]) == 1:
                prefix = getPrefix(delimiterSet)
                innerPropertyDetails += prefix + innerProperty["customRules"][0]
                delimiterSet = True
            else:
                for customRule in innerProperty["customRules"]:
                    innerPropertyDetails += "\n\t- " + customRule
                    # dataModelPropertyDetailExplanations.append("\t-" + customRule + "\n")
        
        innerDataModelExplanation += innerPropertyDetails + "\n"

        # match innerProperty["dataType"]:
        #     case "objects":
        #         objectsProperties.append(innerProperty)
        #     case "uuid":
        #         innerPropertyDetailExplanations.append("\t- " + innerProperty["propertyName"] + ": gültige UUID\n")

        # if "dataTypeDependation" in innerProperty:
        #     for dataType in innerProperty["dataType"]:
        #         if dataType["type"] == "colorString":
        #             suffix = " ein Farbwert in Hexcode sein"
        #         else:
        #             suffix = " ein " + dataType["value"] + " sein"

        #         if "choices" in dataType:
        #             choicesConcatentionString = ""
        #             for choice in dataType["choices"]:
        #                 choicesConcatentionString += choice + ", "
        #             if len(choicesConcatentionString) > 0:
        #                 choicesConcatentionString = choicesConcatentionString[:-2]

        #             suffix += " und einen der folgenden Werte annehmen: " + choicesConcatentionString

        #         innerPropertyDetailExplanations.append("\t- Falls `" + innerProperty["dataTypeDependation"] + '` **"' + dataType["value"] + '"** ist, muss `' + innerProperty["propertyName"] + "`" + suffix + "\n")

        # if "description" in innerProperty and innerProperty["description"] is not None:
        #     innerPropertyDetailExplanations.append("\t- " + innerProperty["propertyName"] + ": " + innerProperty["description"] + "\n")


        # if "fixValue" in innerProperty:
        #     fixValue = innerProperty["fixValue"]
        #     if "fixValueTransformer" in innerProperty:
        #         match innerProperty["fixValueTransformer"]:
        #             case "Stringify":
        #                 fixValue = '"' + fixValue + '"'
        #     innerPropertyDetailExplanations.append("\t- `" + innerProperty["propertyName"] + ": " + fixValue + "\n")
        # if "customRules" in innerProperty:
        #     for customRule in innerProperty["customRules"]:
        #         innerPropertyDetailExplanations.append("\t- " + customRule + "\n")
        # if "choices" in innerProperty and len(innerProperty["choices"]) > 0:
        #     choicesConcatenationString = ""
        #     for choice in innerProperty["choices"]:
        #         choicesConcatenationString += '"' + choice + '", '
        #     # choicesExample = innerProperty["choices"][0]
        #     # if choicesExample.istitle():
        #     #     choicesExampleAlt = choicesExample[0].lower() + choicesExample[1:]
        #     # else:
        #     #     choicesExampleAlt = choicesExample[0].upper() + choicesExample[1:]

        #     choicesConcatenationString = choicesConcatenationString[:-2]
        #     innerPropertyDetailExplanations.append("\t- " + innerProperty["propertyName"] + ": Nur " + choicesConcatenationString + ' (case-sensitive)\n')
    
    # innerPropertyConcatenationString = innerPropertyConcatenationString[:-2]

    # innerDataModelExplanation = "Attribut-Vorgaben (Template.)" + propertyObject["propertyName"] + " ist ein Array von Objekten" + suffix + ", wobei eines dieser Objekte die folgenden Attribute berücksichtigt: " + innerPropertyConcatenationString + "\n"
    # innerDataModelExplanation += "- **Feste Vorgaben für Felder von " + propertyObject["propertyName"] + ":**\n"

    # for innerPropertyDetailExplanation in innerPropertyDetailExplanations:
    #     innerDataModelExplanation += innerPropertyDetailExplanation

    for objectsProperty in objectsProperties:
        recursiveInnerDataModelExplanation = getInnerDataModelExplanation(objectsProperty, propertyPath + "." + propertyObject["propertyName"])
        innerDataModelExplanation += recursiveInnerDataModelExplanation#"- **" + objectsProperty + "** befinden sich auf Top-Level-Ebene im Template und haben folgende Attribute:"
  

    return innerDataModelExplanation

def getRecommendedSteps():
    if not gptFineTuningJson["recommendedStepOrder"] or len(gptFineTuningJson["recommendedStepOrder"]) == 0:
        return ""
    
    recommendedSteps = "\n## Vorgehen bei der Generierung:\n"
    index = 1
    for recommendedStep in gptFineTuningJson["recommendedStepOrder"]:
        recommendedSteps += str(index) + ". " + recommendedStep["step"] + "\n"
        if "implication" in recommendedStep:
            recommendedSteps += "\t → " + recommendedStep["implication"] + "\n"
        
        if "stepSubdivision" in recommendedStep:
            for i, subStep in enumerate(recommendedStep["stepSubdivision"]):
                letter = string.ascii_lowercase[i]  # a, b, c, ...
                recommendedSteps += f"\t{letter}) {subStep['step']}\n"
        
        # if "stepSubdivision" in recommendedSteps:
        #     for subStep in recommendedStep["stepSubdivision"]:
        #         recommendedSteps += "\t" + "a" + ")" + subStep["step"]
        index += 1
    
    return recommendedSteps + "\n"


def getCustomAreaRules() -> str:
    """
    Baut einen Markdown-Block aus gptFineTuningJson["customExplanationAreas"].

    •   Jeder Bereich ->   "### {areaName}"
    •   optionaler       initialExplanation-Text
    •   Regeln als       geordnete 1. 2. 3.  …  oder ungeordnete  "- "
    •   Beliebig tiefe   verschachtelte Unterlisten
    """
    areas: List[Dict[str, Any]] = gptFineTuningJson.get("customExplanationAreas", [])
    if not areas:
        return ""

    lines: List[str] = []                      # gesamtes Markdown

    # -----------------------------------------------------------
    # Helfer zum rekursiven Aufbauen der (Un-)Ordered Lists
    # -----------------------------------------------------------
    def _emit_rules(rule_list: List[Dict[str, Any]],
                    list_type: str = "unorderedList",
                    indent: str = "") -> None:

        if list_type == "orderedList":
            counter = 1
            for r in rule_list:
                lines.append(f"{indent}{counter}. {r['displayText']}")
                if r.get("hasSubRules") and r.get("subRules"):
                    _emit_rules(r["subRules"],
                                r.get("subRuleListType", "unorderedList"),
                                indent + "    ")
                counter += 1
        else:  # unorderedList
            for r in rule_list:
                lines.append(f"{indent}- {r['displayText']}")
                if r.get("hasSubRules") and r.get("subRules"):
                    _emit_rules(r["subRules"],
                                r.get("subRuleListType", "unorderedList"),
                                indent + "    ")

    # -----------------------------------------------------------
    #  Haupt­schleife über alle customExplanationAreas
    # -----------------------------------------------------------
    for area in areas:
        lines.append(f"## {area['areaName']}")
        if area.get("initialExplanation"):
            lines.append(area["initialExplanation"])
        _emit_rules(area["rules"], area.get("ruleListType", "unorderedList"))
        lines.append("")        # Leerzeile nach jedem Block

    return "\n".join(lines)


def getFinalRules():
    if not gptFineTuningJson["finalRules"] or len(gptFineTuningJson["finalRules"]) == 0:
        return ""
    
    finalRulesExplanations = "\n## Zusätzliche Regeln:\n"
    for finalRule in gptFineTuningJson["finalRules"]:
        finalRulesExplanations += "- " + finalRule + "\n"
    
    return finalRulesExplanations

generateGPTFinetuningText()