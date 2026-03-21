<?php
declare(strict_types=1);

namespace DownAccessReport;

use PHPMailer\PHPMailer\Exception as PHPMailerException;
use PHPMailer\PHPMailer\PHPMailer;
use Throwable;

final class DownAccessReportHandler
{
    private const SMTP_HOST     = 'smtp.mail.ovh.net';
    private const SMTP_PORT     = 465;
    private const SMTP_USERNAME = 'app-notification@mathieumartin.ovh';
    private const SMTP_FROM     = 'app-notification@mathieumartin.ovh';
    private const REPORT_TO     = 'contact@mathieumartin.ovh';

    private const SMTP_PASSWORD_ENV = 'APPCLAVIER_SMTP_PASS';
    private const BEARER_SECRET_ENV = 'DOWNACCESS_BEARER_SECRET';

    private const MAX_VERBOSE_LOG_BYTES = 100_000;
    private const MAX_COMMENT_BYTES     = 2_000;

    public function __construct(
        private readonly RateLimiter $rateLimiter,
    ) {
    }

    public function handle(string $requestMethod, string $rawBody, array $server): array
    {
        if (strtoupper($requestMethod) !== 'POST') {
            return [405, $this->error('method_not_allowed', 'Méthode non autorisée.')];
        }

        // Vérification du Bearer token
        $authHeader = trim((string) ($server['HTTP_AUTHORIZATION'] ?? ''));
        $expectedSecret = getenv(self::BEARER_SECRET_ENV) ?: '';
        if ($expectedSecret === '' || $authHeader !== 'Bearer ' . $expectedSecret) {
            return [401, $this->error('unauthorized', 'Accès non autorisé.')];
        }

        $payload = json_decode($rawBody, true);
        if (!is_array($payload)) {
            return [400, $this->error('invalid_json', 'JSON invalide.')];
        }

        $validationError = $this->validate($payload);
        if ($validationError !== null) {
            return [422, $this->error('validation_error', $validationError)];
        }

        $clientIp = $this->resolveClientIp($server);
        try {
            if (!$this->rateLimiter->allow($clientIp)) {
                return [429, $this->error('rate_limited', 'Trop de rapports envoyés récemment.')];
            }
        } catch (Throwable) {
            return [500, $this->error('server_error', "Le rapport n'a pas pu être envoyé.")];
        }

        try {
            $this->sendMail($payload);
        } catch (Throwable $e) {
            return [500, $this->error('server_error', "Envoi email échoué : " . $e->getMessage())];
        }

        return [200, ['ok' => true, 'message' => 'Rapport envoyé avec succès.']];
    }

    private function validate(array $p): ?string
    {
        if (trim((string) ($p['error_message'] ?? '')) === '') {
            return 'Le message d\'erreur est obligatoire.';
        }
        if (trim((string) ($p['app_version'] ?? '')) === '') {
            return 'La version de l\'application est obligatoire.';
        }
        return null;
    }

    private function sendMail(array $p): void
    {
        $smtpPass = getenv(self::SMTP_PASSWORD_ENV) ?: '';
        if ($smtpPass === '') {
            throw new PHPMailerException('SMTP password missing.');
        }

        $appVersion   = $this->str($p, 'app_version');
        $ytdlpVersion = $this->str($p, 'ytdlp_version');
        $os           = $this->str($p, 'os');
        $timestamp    = $this->str($p, 'timestamp');
        $url          = $this->str($p, 'url');
        $site         = $this->str($p, 'site');
        $formatSpec   = $this->str($p, 'format_spec');
        $errorMessage = $this->str($p, 'error_message');
        $verboseLog   = substr($this->str($p, 'verbose_log'), 0, self::MAX_VERBOSE_LOG_BYTES);
        $userComment  = substr($this->str($p, 'user_comment'), 0, self::MAX_COMMENT_BYTES);

        $mailer = new PHPMailer(true);
        $mailer->isSMTP();
        $mailer->Host       = self::SMTP_HOST;
        $mailer->Port       = self::SMTP_PORT;
        $mailer->SMTPAuth   = true;
        $mailer->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS;
        $mailer->Username   = self::SMTP_USERNAME;
        $mailer->Password   = $smtpPass;
        $mailer->CharSet    = 'UTF-8';
        $mailer->Encoding   = 'base64';

        $mailer->setFrom(self::SMTP_FROM, 'DownAccess Error Reporter');
        $mailer->addAddress(self::REPORT_TO);

        $mailer->Subject = sprintf(
            '[DownAccess] Erreur — %s — v%s — %s',
            $site ?: 'inconnu',
            $appVersion,
            gmdate('Y-m-d H:i', strtotime($timestamp) ?: time())
        );

        $mailer->isHTML(true);
        $mailer->Body    = $this->buildHtmlBody(
            $appVersion, $ytdlpVersion, $os, $timestamp,
            $url, $site, $formatSpec, $errorMessage, $verboseLog, $userComment
        );
        $mailer->AltBody = $this->buildTextBody(
            $appVersion, $ytdlpVersion, $os, $timestamp,
            $url, $site, $formatSpec, $errorMessage, $verboseLog, $userComment
        );

        $mailer->send();
    }

    private function buildHtmlBody(
        string $appVersion, string $ytdlpVersion, string $os, string $timestamp,
        string $url, string $site, string $formatSpec, string $errorMessage,
        string $verboseLog, string $userComment
    ): string {
        $h = fn(string $s): string => htmlspecialchars($s, ENT_QUOTES | ENT_HTML5, 'UTF-8');

        $rows = [
            ['Version DownAccess', $appVersion],
            ['Version yt-dlp',     $ytdlpVersion],
            ['Système',            $os],
            ['Date',               $timestamp],
            ['URL',                $url],
            ['Site',               $site],
            ['Format',             $formatSpec],
        ];

        $tableRows = '';
        foreach ($rows as [$label, $value]) {
            $tableRows .= sprintf(
                '<tr><td style="padding:4px 8px;font-weight:bold;white-space:nowrap;">%s</td>'
                . '<td style="padding:4px 8px;word-break:break-all;">%s</td></tr>',
                $h($label),
                $h($value)
            );
        }

        $commentBlock = $userComment !== ''
            ? '<h3>Commentaire utilisateur</h3><p style="background:#fffde7;padding:8px;">' . $h($userComment) . '</p>'
            : '';

        $verboseBlock = $verboseLog !== ''
            ? '<h3>Log diagnostic (yt-dlp verbose)</h3><pre style="background:#f5f5f5;padding:8px;font-size:11px;overflow:auto;">'
              . $h($verboseLog) . '</pre>'
            : '';

        return <<<HTML
        <!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>
        <h2 style="color:#c00;">Rapport d'erreur DownAccess</h2>

        <h3>Informations techniques</h3>
        <table border="1" cellspacing="0" style="border-collapse:collapse;">
        {$tableRows}
        </table>

        <h3>Message d'erreur</h3>
        <pre style="background:#fff0f0;padding:8px;color:#c00;">{$h($errorMessage)}</pre>

        {$commentBlock}
        {$verboseBlock}
        </body></html>
        HTML;
    }

    private function buildTextBody(
        string $appVersion, string $ytdlpVersion, string $os, string $timestamp,
        string $url, string $site, string $formatSpec, string $errorMessage,
        string $verboseLog, string $userComment
    ): string {
        $lines = [
            "RAPPORT D'ERREUR DOWNACCESS",
            str_repeat('=', 40),
            "Version DownAccess : $appVersion",
            "Version yt-dlp     : $ytdlpVersion",
            "Système            : $os",
            "Date               : $timestamp",
            "URL                : $url",
            "Site               : $site",
            "Format             : $formatSpec",
            '',
            "ERREUR :",
            $errorMessage,
        ];

        if ($userComment !== '') {
            $lines[] = '';
            $lines[] = 'COMMENTAIRE UTILISATEUR :';
            $lines[] = $userComment;
        }

        if ($verboseLog !== '') {
            $lines[] = '';
            $lines[] = 'LOG DIAGNOSTIC :';
            $lines[] = $verboseLog;
        }

        return implode(PHP_EOL, $lines);
    }

    private function str(array $p, string $key): string
    {
        $v = $p[$key] ?? '';
        return trim(is_string($v) ? $v : (string) $v);
    }

    private function resolveClientIp(array $server): string
    {
        $forwarded = trim((string) ($server['HTTP_X_FORWARDED_FOR'] ?? ''));
        if ($forwarded !== '') {
            return trim(explode(',', $forwarded)[0]);
        }
        return trim((string) ($server['REMOTE_ADDR'] ?? 'unknown'));
    }

    private function error(string $code, string $message): array
    {
        return ['ok' => false, 'error_code' => $code, 'message' => $message];
    }
}
