import json

def generate_layer(bundle_path, output_path, layer_name="DECOLONIAL.IST Base Layer"):
    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    techniques = []
    all_platforms = set()

    for obj in bundle.get("objects", []):
        if obj.get("type") == "attack-pattern":
            ext_refs = obj.get("external_references", [])
            ext_id = next((ref.get("external_id") for ref in ext_refs if ref.get("source_name") == "mitre-attack"), None)
            
            if not ext_id:
                continue

            platforms = obj.get("x_mitre_platforms", [])
            all_platforms.update(platforms)
            
            # Собираем тактики
            tactics = [p.get("phase_name") for p in obj.get("kill_chain_phases", [])]

            techniques.append({
                "techniqueID": ext_id,
                "tactics": tactics
            })

    layer = {
        "name": layer_name,
        "versions": {
            # attack должен совпадать с version записи в config.json навигатора:
            # слой открывается в домене <domain>-<attack>, и операции над слоями
            # (a+b) работают только в этой версии
            "attack": "18",
            "navigator": "4.9.1",
            "layer": "4.5"
        },
        "domain": "russia-colonialism",
        "showTacticRowBackground": True,
	    "tacticRowBackground": "#dddddd",
	    "selectTechniquesAcrossTactics": False,
	    "selectSubtechniquesWithParent": False,
        "layout":
	    {
	        "layout": "flat",
	        "showName": True,
	        "showID": False
	    },
        "filters": {
            # sorted: порядок set меняется от запуска к запуску, слой выходил разным при тех же данных
            "platforms": sorted(all_platforms)
        },
        "techniques": techniques
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(layer, f, indent=4, ensure_ascii=False)
    
    print(f"Слой сохранен в {output_path}")

if __name__ == "__main__":
    import sys
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else "colonial_with_subtechniques.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "colonial_full_layer.json"
    if len(sys.argv) > 3 and sys.argv[3]:
        generate_layer(bundle_path, output_path, sys.argv[3])
    else:
        generate_layer(bundle_path, output_path)