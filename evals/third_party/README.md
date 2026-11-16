# Third-party code in the eval cases

The `evals/cases/real-*` cases are real commits from public open-source repositories, copied unmodified (the changed files at the parent commit in `before/` and at the commit in `after/`, plus a few neighbour files) by `evals/tools/import_case.py`. Each case's `SOURCE.md` names the repository and commit. Nothing from these repositories is executed. The files keep their original licenses, copied here.

| Repository | License | License file | Cases |
|---|---|---|---|
| https://github.com/pmndrs/zustand | MIT | `zustand-LICENSE` | `real-zustand-use-shallow`, `real-zustand-use-shallow-weakmap`, `real-zustand-shallow-map-set`, `real-zustand-ssr-safe`, `real-zustand-persist-race`, `real-zustand-devtools-cleanup`, `real-zustand-devtools-reviver`, `real-zustand-context-provider` |
| https://github.com/encode/httpx | BSD-3-Clause | `httpx-LICENSE` | `real-httpx-digest-state`, `real-httpx-asgi-exceptions`, `real-httpx-mock-async-handler`, `real-httpx-no-proxy-ip`, `real-httpx-error-request-property`, `real-httpx-zstd-decoder`, `real-httpx-netrc-auth`, `real-httpx-send-timeout` |
| https://github.com/NikolayS/postgres_dba | BSD-3-Clause | `postgres_dba-LICENSE` | `real-pgdba-workload-profile`, `real-pgdba-storage-parameters`, `real-pgdba-buffercache`, `real-pgdba-buffercache-fix`, `real-pgdba-lock-trees`, `real-pgdba-invalid-indexes` |
| https://github.com/dbt-labs/jaffle-shop-classic | Apache-2.0 | `jaffle-shop-classic-LICENSE` | `real-jaffleclassic-join-on`, `real-jaffleclassic-ssms-aliases` |

`dbt-labs/jaffle-shop` (the newer project) was not used: its main branch has no license file.
