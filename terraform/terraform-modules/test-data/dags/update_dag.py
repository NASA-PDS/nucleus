#!/usr/bin/env python3
"""Update DAG summary task to read from EFS files."""

import re

# Read the DAG file
with open('template-pds-validate-and-harvest.py', 'r') as f:
    content = f.read()

# Find and replace the summary task
old_pattern = r'@task\(task_id="Generate_Summary_Report".*?return summary\n'
new_summary = '''@task(task_id="Generate_Summary_Report", trigger_rule=TriggerRule.ALL_DONE, dag=dag)
def generate_summary_report(**context):
    """Generate comprehensive summary report from EFS files."""
    dag_run = context["dag_run"]
    
    batch_id = dag_run.run_id
    efs_config_dir = dag_run.conf.get("efs_config_dir", "")
    
    # Read manifest from EFS
    manifest_products = extract_manifest_products(efs_config_dir)
    
    # Read validation results from EFS
    validated_count = 0
    try:
        with open(f"{efs_config_dir}/validation_results.txt", 'r') as f:
            for line in f:
                if line.startswith("validated_count="):
                    validated_count = int(line.split("=")[1].strip())
    except Exception as e:
        print(f"Could not read validation results: {e}")
    
    # Read harvest results from EFS
    harvested_count = 0
    try:
        with open(f"{efs_config_dir}/harvest_results.txt", 'r') as f:
            for line in f:
                if line.startswith("harvested_count="):
                    harvested_count = int(line.split("=")[1].strip())
    except Exception as e:
        print(f"Could not read harvest results: {e}")
    
    # Calculate data integrity
    manifest_count = len(manifest_products)
    all_match = (manifest_count == validated_count == harvested_count)
    
    # Generate summary report
    summary = {
        "batch_id": batch_id,
        "batch_size": manifest_count,
        "timing": {
            "start_time": dag_run.start_date.isoformat() if dag_run.start_date else None,
            "end_time": datetime.utcnow().isoformat(),
        },
        "manifest": {
            "count": manifest_count,
            "s3_urls": manifest_products,
        },
        "validation": {
            "count": validated_count,
        },
        "harvest": {
            "count": harvested_count,
        },
        "data_integrity": {
            "manifest_count": manifest_count,
            "validated_count": validated_count,
            "harvested_count": harvested_count,
            "all_match": all_match,
            "status": "COMPLETE" if all_match else "INCOMPLETE",
        },
        "status": "SUCCESS" if all_match else "WARNING",
    }
    
    # Log the summary
    summary_json = json.dumps(summary, indent=2)
    print(f"PDS_BATCH_SUMMARY_JSON: {json.dumps(summary)}")
    print(f"\\n=== BATCH SUMMARY REPORT ===")
    print(summary_json)
    print(f"=== END SUMMARY REPORT ===")
    
    return summary

'''

content = re.sub(old_pattern, new_summary, content, flags=re.DOTALL)

# Write back
with open('template-pds-validate-and-harvest.py', 'w') as f:
    f.write(content)

print("Updated DAG summary task")
