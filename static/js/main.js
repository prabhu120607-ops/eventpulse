/**
 * EventPulse Main Client Scripts
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Password visibility toggle
    const togglePasswordButtons = document.querySelectorAll('[data-toggle-password]');
    togglePasswordButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetInputId = btn.getAttribute('data-toggle-password');
            const input = document.getElementById(targetInputId);
            if (input) {
                if (input.type === 'password') {
                    input.type = 'text';
                    btn.innerText = 'Hide';
                } else {
                    input.type = 'password';
                    btn.innerText = 'Show';
                }
            }
        });
    });

    // 2. Auto-dismiss alerts after 6 seconds
    const alerts = document.querySelectorAll('.ep-alert[data-auto-dismiss]');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s ease';
            setTimeout(() => alert.remove(), 500);
        }, 6000);
    });

    // 3. Confirm prompts for destructive actions
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const message = btn.getAttribute('data-confirm') || 'Are you sure you want to proceed?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // 4. Copy to clipboard button
    const copyButtons = document.querySelectorAll('[data-copy-text]');
    copyButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.getAttribute('data-copy-text');
            navigator.clipboard.writeText(text).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = '<span>✓ Copied!</span>';
                setTimeout(() => {
                    btn.innerHTML = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy text: ', err);
            });
        });
    });
});
