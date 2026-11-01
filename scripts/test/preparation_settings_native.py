"""Compare supported automatic choices with the real C++ parser, never the game."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preparation_settings import select


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('RSX_','GT5P_','PAD_'))}
    rows=[]
    with tempfile.TemporaryDirectory(prefix='Tourline settings ') as temp:
        storage=Path(temp)
        settings=storage/'gt5p_settings.toml'
        cases=['', '[video]\nunknown="ignored"', '\ufeff[video]\naspect="21:9"',
               '# 测试\n[video]\naspect="21:9"']
        for resolution in ('"720p"','"1080p"','"1440p"','"2160p"','"4k"','"4K"','720','1080','1440','2160'):
            for aspect in ('16:9','21:9'):
                cases.append('[video]\nresolution='+resolution+'\naspect="'+aspect+'"\n[game]\nanisotropy=16\nsmooth_colour=true\n')
        for text in cases:
            settings.write_text(text,encoding='utf-8')
            original=settings.read_bytes()
            process=subprocess.run([a.probe.resolve()],env=dict(env,GT5P_SETTINGS=str(settings)),
                capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
            assert process.returncode==0,process.stderr
            line=next(row for row in process.stdout.splitlines() if row.startswith('PREPARE_SETTINGS '))
            height,wide,aniso,precision=map(int,line.split()[1:])
            expected='ultrawide-native' if wide else 'native-scaled' if height>1080 else 'default'
            selection=select(storage,{'GT5P_PREPARE_TRANSLATION':'auto'})
            assert selection['mode']==expected,(text,selection,line,process.stderr)
            assert aniso==16 and precision==1
            assert settings.read_bytes()==original
            rows.append(dict(resolution=height,ultrawide=bool(wide),mode=expected))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(dict(cases=len(rows),rows=rows,limitation='Canonical supported file values; custom overrides deliberately fall back to default preparation.'),indent=2)+'\n')
    print(f'{len(rows)} production-parser settings cases passed; no game launched.')


if __name__=='__main__':main()
