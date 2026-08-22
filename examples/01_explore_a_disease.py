"""Explore a CI-validated disease module. Example · not clinical advice."""

from med_research.diseases.base import Disease


def main() -> None:
    disease = Disease("sle")
    print("disease_id:", disease.disease_id)
    print("name:", disease.profile.name)
    print("Research use only. Module presence is not a clinical finding.")


if __name__ == "__main__":
    main()
