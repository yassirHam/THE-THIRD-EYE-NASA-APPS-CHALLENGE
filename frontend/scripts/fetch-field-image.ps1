# Downloads NASA GIBS true-colour tiles (EPSG:4326, 512 px tiles) and stitches them into one JPEG
# for the Two Eyes chapter. NASA imagery is public domain; credit "NASA GIBS / Worldview".
# Usage: powershell -File scripts/fetch-field-image.ps1 -Date 2024-08-15 -Col0 177 -Row0 90 -Out source-textures/field.jpg
# The JPEG is the master. The site ships a WebP encode of it (quality 0.82) in public/tex/, which keeps the download small.
param(
  [string]$Layer = 'VIIRS_SNPP_CorrectedReflectance_TrueColor',
  [string]$Date = '2024-08-15',
  [string]$Matrix = '250m',
  [int]$Zoom = 8,
  [int]$Col0 = 177,
  [int]$Row0 = 90,
  [int]$Cols = 3,
  [int]$Rows = 2,
  [string]$Out = 'source-textures/field.jpg'
)
Add-Type -AssemblyName System.Drawing
$tile = 512
$bmp = New-Object System.Drawing.Bitmap ($tile * $Cols), ($tile * $Rows)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$tmp = Join-Path $env:TEMP 'gibs-tiles'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
for ($r = 0; $r -lt $Rows; $r++) {
  for ($c = 0; $c -lt $Cols; $c++) {
    $row = $Row0 + $r; $col = $Col0 + $c
    $url = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/$Layer/default/$Date/$Matrix/$Zoom/$row/$col.jpg"
    $file = Join-Path $tmp "$Layer-$Date-$Zoom-$row-$col.jpg"
    if (-not (Test-Path $file)) { Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing -TimeoutSec 60 }
    $img = [System.Drawing.Image]::FromFile($file)
    $g.DrawImage($img, $c * $tile, $r * $tile, $tile, $tile)
    $img.Dispose()
  }
}
$g.Dispose()
$codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$params = New-Object System.Drawing.Imaging.EncoderParameters 1
$params.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), 88L
$full = Join-Path (Get-Location) $Out
$bmp.Save($full, $codec, $params)
$bmp.Dispose()
$tileDeg = 288 / [math]::Pow(2, $Zoom)
$lon0 = $Col0 * $tileDeg - 180; $lat0 = 90 - $Row0 * $tileDeg
"saved $Out  lon $lon0 to $($lon0 + $Cols * $tileDeg), lat $lat0 to $($lat0 - $Rows * $tileDeg)"
