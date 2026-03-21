<?php
declare(strict_types=1);

namespace DownAccessReport;

use PHPMailer\PHPMailer\Exception as PHPMailerException;
use PHPMailer\PHPMailer\PHPMailer;
use Throwable;

final class DownAccessContactHandler
{
    private const SMTP_HOST     = 'smtp.mail.ovh.net';
    private const SMTP_PORT     = 465;
    private const SMTP_USERNAME = 'app-notification@mathieumartin.ovh';
    private const SMTP_FROM     = 'app-notification@mathieumartin.ovh';
    private const REPORT_TO     = 'contact@mathieumartin.ovh';

    private const SMTP_PASSWORD_ENV = 'APPCLAVIER_SMTP_PASS';
    private const BEARER_SECRET_ENV = 'DOWNACCESS_BEARER_SECRET';

    private const TYPE_LABELS = [
        'suggestion' => 'Suggestion de fonctionnalité',
        'bug'        => 'Signaler un bug',
        'question'   => 'Question générale',
        'other'      => 'Autre',
    ];

    public function __construct(
        private readonly RateLimiter $rateLimiter,
    ) {
    }

    public function handle(string $requestMethod, string $rawBody, array $server): array
    {
        if (strtoupper($requestMethod) !== 'POST') {
            return [405, $this->error('method_not_allowed', 'Méthode non autorisée.')];
        }

        $authHeader     = trim((string) ($server['HTTP_AUTHORIZATION'] ?? ''));
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
                return [429, $this->error('rate_limited', 'Trop de messages envoyés récemment.')];
            }
        } catch (Throwable) {
            return [500, $this->error('server_error', "Le message n'a pas pu être envoyé.")];
        }

        try {
            $this->sendMail($payload);
        } catch (Throwable $e) {
            return [500, $this->error('server_error', "Envoi email échoué : " . $e->getMessage())];
        }

        return [200, ['ok' => true, 'message' => 'Message envoyé avec succès.']];
    }

    private function validate(array $p): ?string
    {
        $email   = trim((string) ($p['email'] ?? ''));
        $message = trim((string) ($p['message'] ?? ''));

        if ($email === '' || filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
            return "L'adresse email est invalide.";
        }
        if ($message === '') {
            return 'Le message est obligatoire.';
        }
        return null;
    }

    private function sendMail(array $p): void
    {
        $smtpPass = getenv(self::SMTP_PASSWORD_ENV) ?: '';
        if ($smtpPass === '') {
            throw new PHPMailerException('SMTP password missing.');
        }

        $contactType = trim((string) ($p['contact_type'] ?? 'other'));
        $typeLabel   = self::TYPE_LABELS[$contactType] ?? self::TYPE_LABELS['other'];
        $email       = trim((string) ($p['email'] ?? ''));
        $message     = substr(trim((string) ($p['message'] ?? '')), 0, 2000);
        $appVersion  = trim((string) ($p['app_version'] ?? 'inconnue'));

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

        $mailer->setFrom(self::SMTP_FROM, 'DownAccess Contact');
        $mailer->addAddress(self::REPORT_TO);
        $mailer->addReplyTo($email);

        $mailer->Subject = sprintf('[DownAccess] %s — v%s', $typeLabel, $appVersion);

        $h = fn(string $s): string => htmlspecialchars($s, ENT_QUOTES | ENT_HTML5, 'UTF-8');

        $mailer->isHTML(true);
        $mailer->Body = <<<HTML
        <!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>
        <h2>Message de contact — DownAccess</h2>
        <table border="1" cellspacing="0" style="border-collapse:collapse;">
          <tr><td style="padding:4px 8px;font-weight:bold;">Type</td><td style="padding:4px 8px;">{$h($typeLabel)}</td></tr>
          <tr><td style="padding:4px 8px;font-weight:bold;">Email</td><td style="padding:4px 8px;">{$h($email)}</td></tr>
          <tr><td style="padding:4px 8px;font-weight:bold;">Version</td><td style="padding:4px 8px;">{$h($appVersion)}</td></tr>
          <tr><td style="padding:4px 8px;font-weight:bold;">Date</td><td style="padding:4px 8px;">{$h(gmdate('Y-m-d H:i:s'))} UTC</td></tr>
        </table>
        <h3>Message</h3>
        <p style="background:#f5f5f5;padding:12px;white-space:pre-wrap;">{$h($message)}</p>
        </body></html>
        HTML;

        $mailer->AltBody = implode(PHP_EOL, [
            "MESSAGE DE CONTACT DOWNACCESS",
            str_repeat('=', 40),
            "Type    : $typeLabel",
            "Email   : $email",
            "Version : $appVersion",
            "Date    : " . gmdate('Y-m-d H:i:s') . " UTC",
            "",
            "MESSAGE :",
            $message,
        ]);

        $mailer->send();
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
