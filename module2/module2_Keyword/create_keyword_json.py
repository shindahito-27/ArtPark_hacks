from __future__ import annotations

import json
from pathlib import Path

from lay1 import LayerAExtractor


def main() -> None:
    resume_path = Path(
        "/home/kirat/artparl/ArtPark_hacks/module_1_Parse_extractor/main_Resume-2.pdf.txt"
    )
    taxonomy_path = Path(
        "/home/kirat/artparl/ArtPark_hacks/module2/skill_taxonomy_500plus(1).json"
    )
    output_path = Path(
        "/home/kirat/artparl/ArtPark_hacks/module2/module2_Keyword/layer_a_keywords.json"
    )

    text = resume_path.read_text(encoding="utf-8")
    extractor = LayerAExtractor(str(taxonomy_path))
    result = extractor.run(text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    skills_count = len([k for k in result.keys() if not k.startswith("__")])
    print(f"JSON created: {output_path}")
    print(f"Skills extracted: {skills_count}")


if __name__ == "__main__":
    main()
