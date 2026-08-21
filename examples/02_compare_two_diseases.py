"""Point to NosoGraph Compare. Example · experimental · not clinical advice."""

from med_research.biomed.nosograph_compare.service import NosoGraphCompareService


def main() -> None:
    print("NosoGraph Compare is an experimental initial slice.")
    print("Typical pair: sle vs ra. Missingness is explicit.")
    print("engine:", NosoGraphCompareService.__name__)
    print("Use POST /api/v1/nosograph/compare when the API is running.")
    print("Not medical advice.")


if __name__ == "__main__":
    main()
