These four **unmodified public normative schema files** were retrieved from
[SII schema_dte.zip](https://www.sii.cl/factura_electronica/factura_mercado/schema_dte.zip)
on 2026-10-30. ZIP SHA256:
`59429e27879824e9eecb0942cee733f7cf93cb61f8b80d5f5a34bcd22b6c5bee`.
They are reference data published by SII, not Odoo Enterprise sources or Steps
LGPL source code. Retain their original notices, bytes and ISO-8859-1 encoding.
The XML signature schema retains its W3C Software License notice and links.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| EnvioDTE_v10.xsd | 4738 | 33ea8dd38c895c359dddbcd21feb5acf8a4717f7f67524a6b0dd9a83d76920eb |
| DTE_v10.xsd | 236960 | 85518401b7dddac1bc0b7b99646a1ce353a4afa645344ea5f10af3a2e6676b37 |
| SiiTypes_v10.xsd | 30383 | ce9a84bde70aa9d0f9269d99acd3b0ea81d868022517ac31064b6cdfa0c45bdf |
| xmldsignature_v10.xsd | 7135 | 427e3225cd379ae92bae464b892dbf964665af92d453ac61774cffab38b95edb |

`dte_schema.py` verifies all four pins before compiling DTE_v10.xsd. Its
resolver admits only these exact in-memory files; no network, filesystem URL,
parent traversal or fallback resolver is allowed. The directory's Git
attributes disable line-ending conversion and text diff for the immutable
reference binaries, including their original CRLF and trailing whitespace.
EnvioDTE is retained for provenance completeness; this API validates a single
DTE and does not construct or certify an EnvioDTE envelope.
