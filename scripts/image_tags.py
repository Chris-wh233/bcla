#!/usr/bin/env python3
"""List all LCR tags, following server pagination before returning any results."""

import argparse
import json
import re
import sys
from urllib.parse import urljoin, urlsplit
from urllib.request import ProxyHandler, build_opener


def next_page(headers, current):
    links = []
    for header in headers.get_all("Link", []):
        for match in re.finditer(r'<([^>]+)>\s*((?:;[^,<]*)*)', header):
            relation = re.search(r';\s*rel\s*=\s*(?:"([^"]*)"|([^;\s]+))', match[2], re.I)
            if relation and "next" in (relation[1] or relation[2]).split():
                links.append(urljoin(current, match[1]))
    if len(set(links)) > 1:
        raise ValueError("Conflicting next-page links")
    return links[0] if links else None


def list_tags(repository, direct=False):
    if not re.fullmatch(r'[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+', repository):
        raise ValueError("Expected a repository path such as library/golang")
    url = f"https://lcr.loongnix.cn/v2/{repository}/tags/list?n=1000"
    opener = build_opener(ProxyHandler({})) if direct else build_opener()
    visited, tags = set(), set()
    while url:
        if url in visited:
            raise ValueError("Pagination loop; tag discovery is incomplete")
        if urlsplit(url).netloc != "lcr.loongnix.cn" or urlsplit(url).scheme != "https":
            raise ValueError("Unexpected pagination origin")
        visited.add(url)
        with opener.open(url, timeout=30) as response:
            body = json.load(response)
            page_tags = body.get("tags")
            if body.get("name") != repository or not isinstance(page_tags, (list, type(None))):
                raise ValueError("Invalid tag-list response")
            if any(not isinstance(tag, str) for tag in page_tags or []):
                raise ValueError("Invalid tag value")
            tags.update(page_tags or [])
            url = next_page(response.headers, response.geturl())
    return dict(repository=repository, complete=True, pages=len(visited), count=len(tags), tags=sorted(tags))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="LCR repository, e.g. library/golang")
    parser.add_argument("--direct", action="store_true", help="Ignore environment HTTP proxies for this query")
    args = parser.parse_args()
    try:
        print(json.dumps(list_tags(args.repository, args.direct), ensure_ascii=False, indent=2))
    except Exception as error:
        print(json.dumps(dict(complete=False, error=str(error))), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
