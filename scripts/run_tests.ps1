# Pruebas de integración básicas para NueveOnce
# Requiere que el servidor esté corriendo en http://127.0.0.1:5000

function fail($msg) {
    Write-Error $msg
    exit 1
}

$base = 'http://127.0.0.1:5000'

Write-Output "Test 1: dolor pecho -> esperar Nivel 1"
$body = @{nombre='test_integ_1'} | ConvertTo-Json -Compress
$p = Invoke-RestMethod -Uri "$base/api/patient" -Method Post -Body $body -ContentType 'application/json'
$body = @{sintomas='dolor pecho'; paciente_id=$p.paciente_id} | ConvertTo-Json -Compress
$t = Invoke-RestMethod -Uri "$base/api/triage" -Method Post -Body $body -ContentType 'application/json'
if ($t.nivel -ne 1) { fail "Fallo: nivel esperado 1, obtenido $($t.nivel)" }
Write-Output "-> Nivel correcto: $($t.nivel)"

$sid = $t.session_id
# responder follow-ups
$b = @{session_id=$sid; answer='si'} | ConvertTo-Json -Compress
$r = Invoke-RestMethod -Uri "$base/api/triage/answer" -Method Post -Body $b -ContentType 'application/json'
$b = @{session_id=$sid; answer='no'} | ConvertTo-Json -Compress
$r = Invoke-RestMethod -Uri "$base/api/triage/answer" -Method Post -Body $b -ContentType 'application/json'
if ($r.session.nivel -ne 1) { fail "Fallo after followups: nivel esperado 1, obtenido $($r.session.nivel)" }
Write-Output "-> Follow-up OK, nivel final: $($r.session.nivel)"

Write-Output "Test 2: caída cabeza -> esperar Nivel 3 (por reglas)"
$body = @{nombre='test_integ_2'} | ConvertTo-Json -Compress
$p2 = Invoke-RestMethod -Uri "$base/api/patient" -Method Post -Body $body -ContentType 'application/json'
$body = @{sintomas='mi hermana se callo por las escalas y tiene un chichon en la cabeza'; paciente_id=$p2.paciente_id} | ConvertTo-Json -Compress
$t2 = Invoke-RestMethod -Uri "$base/api/triage" -Method Post -Body $body -ContentType 'application/json'
if ($t2.nivel -ne 3) { fail "Fallo: nivel esperado 3, obtenido $($t2.nivel)" }
Write-Output "-> Nivel inicial correcto: $($t2.nivel)"

$sid2 = $t2.session_id
$b = @{session_id=$sid2; answer='2 dias'} | ConvertTo-Json -Compress
$r = Invoke-RestMethod -Uri "$base/api/triage/answer" -Method Post -Body $b -ContentType 'application/json'
$b = @{session_id=$sid2; answer='no'} | ConvertTo-Json -Compress
$r = Invoke-RestMethod -Uri "$base/api/triage/answer" -Method Post -Body $b -ContentType 'application/json'
$b = @{session_id=$sid2; answer='no'} | ConvertTo-Json -Compress
$r = Invoke-RestMethod -Uri "$base/api/triage/answer" -Method Post -Body $b -ContentType 'application/json'
if ($r.session.nivel -ne 3) { fail "Fallo after followups: nivel esperado 3, obtenido $($r.session.nivel)" }
Write-Output "-> Follow-up OK, nivel final: $($r.session.nivel)"

Write-Output "Todas las pruebas pasaron correctamente."
exit 0
