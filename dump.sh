

OUT="src_dump.txt"
rm -f "$OUT"

# Header
{
  echo "===== tracker-steps / src dump ====="
  echo "Generated at: $(date -Is)"
  echo "Working dir: $(pwd)"
  echo ""
} >> "$OUT"

# Dump ordenado por path, con separadores
find src -type f \
  ! -path "src/assets/*" \
  -print0 | sort -z |
while IFS= read -r -d '' f; do
  # Saltar archivos no-texto por si acaso
  if file "$f" | grep -qiE 'text|json|xml|javascript|typescript|css|html|svg'; then
    {

      echo "FILE: $f"
      cat "$f"
 
    } >> "$OUT"
  else
    {

      echo "FILE: $f"
    } >> "$OUT"
  fi
done

echo "Listo: $OUT"
