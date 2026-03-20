import os
import subprocess
import sys
from pathlib import Path

INPUT_RESUME = "AnjaliSharma_Resume (4).pdf"
INPUT_JOB_DESC = "Machine-Learning-Engineer.pdf"
OUTPUT_DIR = "output"
OUTPUT_DIR_MODULE_1 = "output/resume/module_1"
OUTPUT_DIR_MODULE_2 = "output/resume/module_2"
OUTPUT_DIR_MODULE_2_A = "output/resume/module_2/A"
OUTPUT_DIR_MODULE_2_B = "output/resume/module_2/B"
OUTPUT_DIR_MODULE_3 = "output/jd/module_3"
OUTPUT_DIR_MODULE_3_COMBINED = "output/jd/module_3/COMBINED"
OUTPUT_DIR_MODULE_3_KEYWORD = "output/jd/module_3/module2_Keyword"
OUTPUT_DIR_MODULE_3_SEMANTIC = "output/jd/module_3/module2_semantic"
OUTPUT_DIR_MODULE_4 = "output/module_4"
OUTPUT_DIR_MODULE_5 = "output/module_5"




def run_pipeline(input_dir_resume, input_dir_job_desc, output_dir):
    # Create output directories if they don't exist.
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_1, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_2, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_2_A, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_2_B, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_3, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_3_COMBINED, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_3_KEYWORD, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_3_SEMANTIC, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_4, exist_ok=True)
    os.makedirs(OUTPUT_DIR_MODULE_5, exist_ok=True)
    # Run module 1 resume parser and write its text output to module_1 output folder.
    module_1_script = Path("ArtPark_hacks/ArtPark_hacks/module_1_Parse_extractor/main_extraction.py")
    subprocess.run(
        [sys.executable, str(module_1_script), input_dir_resume, OUTPUT_DIR_MODULE_1],
        check=True,
    )

    # Run module 2A keyword extractor on module 1 output text.
    module_2_A_script = Path("ArtPark_hacks/ArtPark_hacks/module2/module2_Keyword/lay1.py")
    module_1_output_txt = Path(OUTPUT_DIR_MODULE_1) / f"{Path(input_dir_resume).stem}.txt"
    module_2_taxonomy = Path("skill_taxonomy_500plus(1).json")
    module_2_A_output_json = Path(OUTPUT_DIR_MODULE_2_A) / "layer_a_keywords.json"

    subprocess.run(
        [
            sys.executable,
            str(module_2_A_script),
            str(module_1_output_txt),
            str(module_2_taxonomy),
            str(module_2_A_output_json),
        ],
        check=True,
    )

    # Run module 2B semantic extractor on module 1 output text.
    module_2_B_script = Path("ArtPark_hacks/ArtPark_hacks/module2/module2_semantic/generate_resume_skill_json.py")
    module_2_B_taxonomy = Path("skill_taxonomy_500plus(1).json")
    module_2_B_output_json = Path(OUTPUT_DIR_MODULE_2_B) / "layer_a_semantic_resume.json"

    subprocess.run(
        [
            sys.executable,
            str(module_2_B_script),
            str(module_1_output_txt),
            str(module_2_B_taxonomy),
            str(module_2_B_output_json),
        ],
        check=True,
    )

    module_2_combine_script = Path("ArtPark_hacks/ArtPark_hacks/module2/combine.py")
    module_2_combined_output_json = Path(OUTPUT_DIR_MODULE_2) / "Module_2_combined.json"

    subprocess.run(
            [
            sys.executable,
            str(module_2_combine_script),
            str(module_2_A_output_json),
            str(module_2_B_output_json),
            str(module_2_combined_output_json),
        ],
        check=True,
    )

    # Run module 3 JD parser first.
    module_3_parser_script = Path("ArtPark_hacks/ArtPark_hacks/module_3_jd/run_jd_parser.py")
    module_3_jd_text_output = Path(OUTPUT_DIR_MODULE_3) / "jd_resulting_text.txt"
    module_3_jd_json_output = Path(OUTPUT_DIR_MODULE_3) / "jd_parsed_output.json"

    subprocess.run(
        [
            sys.executable,
            str(module_3_parser_script),
            "--input",
            str(input_dir_job_desc),
            "--txt-out",
            str(module_3_jd_text_output),
            "--json-out",
            str(module_3_jd_json_output),
        ],
        check=True,
    )

    # Then run module 3 keyword + semantic + combined scoring pipeline.
    module_3_scoring_script = Path("ArtPark_hacks/ArtPark_hacks/module_3_jd/jd_req/run_jd_scoring_pipeline.py")
    module_3_taxonomy = Path("ArtPark_hacks/ArtPark_hacks/module_3_jd/jd_req/skill_taxonomy_500plus(1).json")
    module_3_keyword_json = Path(OUTPUT_DIR_MODULE_3_KEYWORD) / "layer_a_keywords.json"
    module_3_semantic_json = Path(OUTPUT_DIR_MODULE_3_SEMANTIC) / "layer_a_semantic_resume.json"
    module_3_combined_json = Path(OUTPUT_DIR_MODULE_3_COMBINED) / "layer_a_combined_scored.json"

    subprocess.run(
        [
            sys.executable,
            str(module_3_scoring_script),
            "--jd-text",
            str(module_3_jd_text_output),
            "--taxonomy",
            str(module_3_taxonomy),
            "--keyword-json",
            str(module_3_keyword_json),
            "--semantic-json",
            str(module_3_semantic_json),
            "--combined-json",
            str(module_3_combined_json),
        ],
        check=True,
    )

    # Run module 4 gap engine using module 2 + module 3 combined outputs.
    module_4_gapengine_script = Path("ArtPark_hacks/ArtPark_hacks/module4/gapengine.py")
    module_4_output_json = Path(OUTPUT_DIR_MODULE_4) / "gapengine_output.json"

    subprocess.run(
        [
            sys.executable,
            str(module_4_gapengine_script),
            str(module_2_combined_output_json),
            str(module_3_combined_json),
            "-o",
            str(module_4_output_json),
        ],
        check=True,
    )

    # Run module 5 profession mapper using the resume skill scores.
    module_5_mapper_script = Path("ArtPark_hacks/ArtPark_hacks/module5/profession_mapper.py")
    module_5_dataset_json = Path("ArtPark_hacks/ArtPark_hacks/module5/profession_mapping_engine_dataset_v7.json")
    module_5_output_json = Path(OUTPUT_DIR_MODULE_5) / "profession_mapping_output.json"

    subprocess.run(
        [
            sys.executable,
            str(module_5_mapper_script),
            str(module_2_combined_output_json),
            str(module_5_dataset_json),
            str(module_5_output_json),
        ],
        check=True,
    )


if __name__ == "__main__":
    run_pipeline(INPUT_RESUME, INPUT_JOB_DESC, OUTPUT_DIR)
