import hashlib
import os
from pathlib import Path
import pytest
from sapera import core
from sapera.cli import load_db, extract_program, patch_container_exact

CASES = {
    "a00uad02": (0x000949A8, "SAPERA_P911_AAE_RAW"),
    "a00kac02": (0x000947E8, "SAPERA_P911_KAC_RAW"),
}

@pytest.mark.parametrize("build", sorted(CASES))
def test_distribution_profile_has_exact_original_checks(build):
    db=load_db()
    matches=[x for x in db["builds"].values() if any(build in aliases.replace(" / ", "|").split("|") for aliases in x["chds"])]
    assert len(matches)==1
    item=matches[0]
    assert item["default_profile"]=="erased_u39_distribution_recovery"
    p=item["profiles"]["erased_u39_distribution_recovery"]
    assert p["status"]=="runtime_advanced"
    assert len(p["patches"])==6
    extra=p["patches"][-1]
    assert int(extra["address"],16)==CASES[build][0]
    assert extra["original"]=="4182002c"
    assert extra["replacement"]=="60000000"

@pytest.mark.parametrize("build", sorted(CASES))
def test_distribution_recovery_optional_real_media(build):
    env=CASES[build][1]
    path=os.environ.get(env)
    if not path: pytest.skip(f"provide {env} to test with original user-owned media")
    original=Path(path).read_bytes()
    game,loc,desc,program,_=extract_program(original)
    target,report=patch_container_exact(original,load_db(),"erased_u39_distribution_recovery",True,False,"neutral")
    tbin,tloc,td,tprog,_=extract_program(target)
    assert td.comp_size==desc.comp_size and td.checksum==desc.checksum
    assert len(original)==len(target)
    assert sum(tbin[td.stream_off:td.stream_off+td.comp_size])==sum(game[desc.stream_off:desc.stream_off+desc.comp_size])
    site=CASES[build][0]-desc.load_addr
    assert program[site:site+4].hex()=="4182002c"
    assert tprog[site:site+4].hex()=="60000000"
    assert report["neutral_report"]["backend"]=="verified-manifest"
