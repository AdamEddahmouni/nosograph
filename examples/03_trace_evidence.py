"""Evidence tracing reminder. Example · not clinical advice."""

from med_research.pipeline.evidence_workspace import schemas


def main() -> None:
    print("Trace: condition → claim → evidence → provenance → source snapshot")
    print("schema_module:", schemas.__name__)
    print("Computational hypothesis only. Not a causal or clinical conclusion.")


if __name__ == "__main__":
    main()
