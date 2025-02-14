#!/usr/bin/env python3

import os
import subprocess

import requests
import yaml


def download(session, url, fn):
    if os.path.exists(fn):
        print(f'Removing old file {fn}')
        os.unlink(fn)
    print(f'Downloading {fn} from {url}')
    with open(fn, 'wb') as f:
        r = session.get(url, stream=True)
        r.raise_for_status()
        for c in r.iter_content(1024):
            f.write(c)


def get_current_tag():
    out = subprocess.check_output(['git', 'tag', '--points-at', 'HEAD']).strip()
    if not out:
        raise RuntimeError('Could not find any tags pointing to current release')
    tags = out.decode('utf-8').split(' ')
    if len(tags) > 1:
        raise RuntimeError(f'More than one tag points to HEAD: {tags}')
    return tags[0]


def find_release_by_name(s, name):
    r = s.get("https://api.github.com/repos/buildbot/buildbot/releases")
    r.raise_for_status()
    for release in r.json():
        if release['name'] == name:
            return release

    raise RuntimeError(f'Could not find release for name {name}')


def main():
    with open(os.path.expanduser("~/.config/hub")) as f:
        conf = yaml.safe_load(f)
        token = conf['github.com'][0]['oauth_token']

    s = requests.Session()
    s.headers.update({'Authorization': 'token ' + token})

    tag = get_current_tag()
    release = find_release_by_name(s, name=tag)

    upload_url = release['upload_url'].split('{')[0]
    assets = s.get(
        ("https://api.github.com/repos/buildbot/buildbot/releases/{id}/assets").format(
            id=release['id']
        )
    )
    assets.raise_for_status()
    assets = assets.json()
    os.makedirs('dist', exist_ok=True)
    for url in (a['browser_download_url'] for a in assets):
        if 'gitarchive' in url:
            raise RuntimeError(
                'The git archive has already been uploaded. Are you trying to fix '
                'broken upload? If this is the case, delete the asset in the GitHub '
                'UI and retry this command'
            )
        if url.endswith(".whl") or url.endswith(".tar.gz"):
            fn = os.path.join('dist', url.split('/')[-1])
            download(s, url, fn)
    # download tag archive
    url = f"https://github.com/buildbot/buildbot/archive/{tag}.tar.gz"
    fn = os.path.join('dist', f"buildbot-{tag}.gitarchive.tar.gz")
    download(s, url, fn)
    sigfn = fn + ".asc"
    if os.path.exists(sigfn):
        os.unlink(sigfn)
    # sign the tag archive for debian
    os.system(f"gpg --armor --detach-sign --output {sigfn} {fn}")
    sigfnbase = os.path.basename(sigfn)
    r = s.post(
        upload_url,
        headers={'Content-Type': "application/pgp-signature"},
        params={"name": sigfnbase},
        data=open(sigfn, 'rb'),
    )
    print(r.content)
    fnbase = os.path.basename(fn)
    r = s.post(
        upload_url,
        headers={'Content-Type': "application/gzip"},
        params={"name": fnbase},
        data=open(fn, 'rb'),
    )
    print(r.content)
    # remove files so that twine upload do not upload them
    os.unlink(sigfn)
    os.unlink(fn)


if __name__ == '__main__':
    main()
