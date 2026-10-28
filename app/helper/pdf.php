<?php

namespace Helper;

/**
 * Minimal dependency-free PDF writer for tabular reports (A4 landscape, Helvetica).
 *
 * Usage:
 *   $pdf = new \Helper\Pdf('Title', 'Subtitle');
 *   $pdf->heading('Section');
 *   $pdf->table(['Name', 'Value'], [['a', 1]], [3, 1]);
 *   $pdf->output('report.pdf');
 */
class Pdf
{
    private const W = 842;
    private const H = 595;
    private const MARGIN = 40;
    private const ROW = 17;

    /** @var string[] Content stream per page */
    private array $pages = [];
    private float $y = 0;
    private string $footer;

    public function __construct(private readonly string $title, string $subtitle = '')
    {
        $this->footer = $title . ' - generated ' . gmdate('Y-m-d H:i') . ' UTC';
        $this->newPage();
        $this->text(self::MARGIN, $this->y, $title, 18, true);
        $this->y -= 20;
        if ($subtitle !== '') {
            $this->text(self::MARGIN, $this->y, $subtitle, 10, false, [0.4, 0.4, 0.47]);
            $this->y -= 10;
        }

        $this->y -= 14;
    }

    public function heading(string $text): void
    {
        $this->ensure(50);
        $this->y -= 8;
        $this->text(self::MARGIN, $this->y, $text, 13, true, [0.25, 0.2, 0.6]);
        $this->y -= 18;
    }

    public function paragraph(string $text): void
    {
        $this->ensure(20);
        $this->text(self::MARGIN, $this->y, $text, 9.5, false, [0.4, 0.4, 0.47]);
        $this->y -= 16;
    }

    /**
     * @param string[] $headers
     * @param array[]  $rows    Rows of scalar cells
     * @param float[]  $weights Relative column widths
     */
    public function table(array $headers, array $rows, array $weights = []): void
    {
        $n = count($headers);
        $weights = count($weights) === $n ? $weights : array_fill(0, $n, 1);
        $usable = self::W - 2 * self::MARGIN;
        if ($n < 5) {
            // Keep narrow tables compact instead of stretching them across the page
            $usable = min($usable, $n * 190);
        }

        $sum = array_sum($weights);
        $widths = array_map(fn ($w) => $usable * $w / $sum, $weights);

        if (!$rows) {
            $this->paragraph('No data.');
            return;
        }

        $head = function () use ($headers, $widths): void {
            $this->rect(self::MARGIN, $this->y - 5, self::W - 2 * self::MARGIN, self::ROW, [0.93, 0.92, 0.98]);
            $x = self::MARGIN + 4;
            foreach ($headers as $i => $h) {
                $this->text($x, $this->y, $this->fit((string) $h, $widths[$i] - 8, 8.5, true), 8.5, true);
                $x += $widths[$i];
            }

            $this->y -= self::ROW;
        };

        $this->ensure(self::ROW * 3);
        $head();
        foreach ($rows as $k => $row) {
            if ($this->y < self::MARGIN + 30) {
                $this->newPage();
                $head();
            }

            if ($k % 2 === 1) {
                $this->rect(self::MARGIN, $this->y - 5, self::W - 2 * self::MARGIN, self::ROW, [0.975, 0.975, 0.985]);
            }

            $x = self::MARGIN + 4;
            foreach (array_values($row) as $i => $cell) {
                $this->text($x, $this->y, $this->fit((string) $cell, $widths[$i] - 8, 8.5, false), 8.5, false);
                $x += $widths[$i];
            }

            $this->y -= self::ROW;
        }

        $this->y -= 6;
    }

    /**
     * Send the document to the browser as a download.
     */
    public function output(string $filename): void
    {
        $pdf = $this->build();
        if (!headers_sent()) {
            header('Content-Type: application/pdf');
            header('Content-Disposition: attachment; filename="' . preg_replace('/[^A-Za-z0-9._-]/', '_', $filename) . '"');
            header('Content-Length: ' . strlen($pdf));
        }

        echo $pdf;
    }

    public function build(): string
    {
        $total = count($this->pages);
        $objects = [];
        $objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
        $kids = [];
        $objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>';
        $objects[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>';
        $id = 5;
        foreach ($this->pages as $i => $content) {
            $content .= $this->rawText(self::MARGIN, 22, $this->footer, 7.5, false, [0.55, 0.55, 0.6])
                . $this->rawText(self::W - self::MARGIN - 40, 22, 'Page ' . ($i + 1) . '/' . $total, 7.5, false, [0.55, 0.55, 0.6]);
            $objects[$id] = "<< /Length " . strlen($content) . " >>\nstream\n" . $content . "\nendstream";
            $objects[$id + 1] = '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ' . self::W . ' ' . self::H . '] '
                . '/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ' . $id . ' 0 R >>';
            $kids[] = ($id + 1) . ' 0 R';
            $id += 2;
        }

        $objects[2] = '<< /Type /Pages /Kids [' . implode(' ', $kids) . '] /Count ' . count($kids) . ' >>';
        ksort($objects);

        $out = "%PDF-1.4\n";
        $offsets = [];
        foreach ($objects as $num => $body) {
            $offsets[$num] = strlen($out);
            $out .= $num . " 0 obj\n" . $body . "\nendobj\n";
        }

        $xref = strlen($out);
        $out .= "xref\n0 " . (count($objects) + 1) . "\n0000000000 65535 f \n";
        foreach ($offsets as $off) {
            $out .= sprintf("%010d 00000 n \n", $off);
        }

        $out .= "trailer\n<< /Size " . (count($objects) + 1) . " /Root 1 0 R /Info << /Title (" . $this->esc($this->title) . ") >> >>\n";
        $out .= "startxref\n" . $xref . "\n%%EOF";

        return $out;
    }

    private function newPage(): void
    {
        $this->pages[] = '';
        $this->y = self::H - self::MARGIN;
    }

    private function ensure(float $needed): void
    {
        if ($this->y - $needed < self::MARGIN) {
            $this->newPage();
        }
    }

    private function cur(): int
    {
        return count($this->pages) - 1;
    }

    private function text(float $x, float $y, string $s, float $size, bool $bold, array $rgb = [0.1, 0.1, 0.15]): void
    {
        $this->pages[$this->cur()] .= $this->rawText($x, $y, $s, $size, $bold, $rgb);
    }

    private function rawText(float $x, float $y, string $s, float $size, bool $bold, array $rgb): string
    {
        return sprintf("BT %.2F %.2F %.2F rg /%s %.1F Tf %.2F %.2F Td (%s) Tj ET\n", $rgb[0], $rgb[1], $rgb[2], $bold ? 'F2' : 'F1', $size, $x, $y, $this->esc($s));
    }

    private function rect(float $x, float $y, float $w, float $h, array $rgb): void
    {
        $this->pages[$this->cur()] .= sprintf("%.2F %.2F %.2F rg %.2F %.2F %.2F %.2F re f\n", $rgb[0], $rgb[1], $rgb[2], $x, $y, $w, $h);
    }

    /** Truncate to the available width using an average glyph width estimate. */
    private function fit(string $s, float $width, float $size, bool $bold): string
    {
        $s = preg_replace('/\s+/', ' ', $s) ?? '';
        $max = max(1, (int) floor($width / ($size * ($bold ? 0.56 : 0.5))));
        if (mb_strlen($s) > $max) {
            $s = mb_substr($s, 0, max(1, $max - 1)) . '...';
        }

        return $s;
    }

    private function esc(string $s): string
    {
        $conv = @iconv('UTF-8', 'windows-1252//TRANSLIT//IGNORE', $s);
        $s = $conv === false ? preg_replace('/[^\x20-\x7E]/', '?', $s) : $conv;

        return str_replace(['\\', '(', ')', "\r", "\n"], ['\\\\', '\\(', '\\)', ' ', ' '], (string) $s);
    }
}
