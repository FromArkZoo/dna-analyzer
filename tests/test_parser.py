import io
import zipfile

from analyzers.parser import parse_ancestry_file


def _read(path):
    with open(path) as f:
        return io.StringIO(f.read())


def test_parse_ancestry_format():
    g = parse_ancestry_file(_read("tests/fixtures/ancestry_sample.txt"))
    assert g["rs1801133"] == ("A", "G")
    assert g["rs4988235"] == ("A", "A")


def test_parse_23andme_format():
    g = parse_ancestry_file(_read("tests/fixtures/23andme_sample.txt"))
    assert g["rs1801133"] == ("A", "G")
    assert g["rs4988235"] == ("A", "A")


def test_parse_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_ancestry_file(io.StringIO("# only comments\n"))


def test_zip_unwrap_returns_text():
    from analyzers.parser import read_genotype_text

    with open("tests/fixtures/23andme_sample.txt", "rb") as f:
        inner = f.read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("genome.txt", inner)
    text = read_genotype_text(buf.getvalue(), "genome.zip")
    assert "rs1801133" in text


def test_read_genotype_text_plain_passthrough():
    from analyzers.parser import read_genotype_text
    raw = b"rs1\t1\t1\tA\tG\n"
    assert read_genotype_text(raw, "x.txt") == "rs1\t1\t1\tA\tG\n"


def test_zip_roundtrip_parses_genotypes():
    from analyzers.parser import read_genotype_text
    with open("tests/fixtures/23andme_sample.txt", "rb") as f:
        inner = f.read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("genome.txt", inner)
    text = read_genotype_text(buf.getvalue(), "genome.zip")
    g = parse_ancestry_file(io.StringIO(text))
    assert g["rs1801133"] == ("A", "G")
    assert g["rs4988235"] == ("A", "A")


def test_corrupt_zip_raises_valueerror():
    import pytest
    from analyzers.parser import read_genotype_text
    with pytest.raises(ValueError):
        read_genotype_text(b"this is not a zip file", "broken.zip")
