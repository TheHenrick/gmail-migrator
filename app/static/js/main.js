/**
 * Gmail Migrator - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const connectGmailBtn = document.getElementById('connectGmail');
    const connectDestinationBtn = document.getElementById('connectDestination');
    const startMigrationBtn = document.getElementById('startMigration');
    const accountOptions = document.querySelectorAll('.account-option');
    const migrationStatus = document.getElementById('migrationStatus');
    const progressBarFill = document.getElementById('progressBarFill');
    const processedCount = document.getElementById('processedCount');
    const progressPercentage = document.getElementById('progressPercentage');
    const successCount = document.getElementById('successCount');
    const pendingCount = document.getElementById('pendingCount');
    const failedCount = document.getElementById('failedCount');
    const migrationLog = document.getElementById('migrationLog');
    const pauseResumeMigrationBtn = document.getElementById('pauseResumeMigration');
    const cancelMigrationBtn = document.getElementById('cancelMigration');
    const downloadReportBtn = document.getElementById('downloadReport');
    const batchProcessingCheckbox = document.getElementById('batchProcessing');
    const batchSizeContainer = document.getElementById('batchSizeContainer');
    const batchSizeSlider = document.getElementById('batchSizeSlider');
    const batchSizeValue = document.getElementById('batchSizeValue');

    // State
    let isGmailConnected = false;
    let isDestinationConnected = false;
    let selectedDestination = null;
    let migration = {
        status: 'idle', // idle, running, paused, completed, failed, cancelled
        total: 0,
        processed: 0,
        successful: 0,
        failed: 0,
        pending: 0,
        logs: [],
        batchSize: 50,
        isBatchProcessing: true,
        options: {
            preserveFolders: true,
            includeAttachments: true,
            onlyUnread: false,
            startDate: null,
            endDate: null
        }
    };

    // Initialize batch size slider
    batchSizeSlider.addEventListener('input', () => {
        const value = batchSizeSlider.value;
        batchSizeValue.textContent = `${value} emails`;
        migration.batchSize = parseInt(value);
    });

    // Toggle batch size container based on batch processing checkbox
    batchProcessingCheckbox.addEventListener('change', () => {
        migration.isBatchProcessing = batchProcessingCheckbox.checked;
        batchSizeContainer.style.display = batchProcessingCheckbox.checked ? 'block' : 'none';
    });

    // Initially hide batch size container if batch processing is disabled
    batchSizeContainer.style.display = batchProcessingCheckbox.checked ? 'block' : 'none';

    // Connect Gmail button
    connectGmailBtn.addEventListener('click', async () => {
        try {
            // Redirect to the backend endpoint to start OAuth flow
            const response = await fetch('/gmail/auth-url');
            const data = await response.json();

            // Store the state for CSRF protection
            localStorage.setItem('gmailOAuthState', data.state);

            // Redirect to Google's authorization page
            window.location.href = data.auth_url;
        } catch (error) {
            logToConsole(`Error connecting to Gmail: ${error.message}`, 'error');
        }
    });

    // Destination account selection
    accountOptions.forEach(option => {
        if (option.closest('.source-section')) return; // Skip source options

        option.addEventListener('click', () => {
            // Remove selection from all options
            accountOptions.forEach(opt => {
                if (opt.closest('.destination-section')) {
                    opt.classList.remove('selected');
                }
            });

            // Add selection to clicked option
            option.classList.add('selected');
            selectedDestination = option.getAttribute('data-provider');

            logToConsole(`Selected destination: ${selectedDestination}`);

            // Enable connect destination button
            connectDestinationBtn.disabled = false;

            updateUI();
        });
    });

    // Connect destination button
    connectDestinationBtn.addEventListener('click', async () => {
        if (!selectedDestination) {
            logToConsole('Please select a destination service', 'warning');
            return;
        }

        try {
            logToConsole(`Initiating ${selectedDestination} OAuth flow...`);
            connectDestinationBtn.textContent = 'Connecting...';
            connectDestinationBtn.disabled = true;

            // Make API call to get auth URL for selected destination
            const response = await fetch(`/${selectedDestination}/auth-url`);
            const data = await response.json();

            // Store the state for CSRF protection if provided
            if (data.state) {
                localStorage.setItem(`${selectedDestination}OAuthState`, data.state);
            }

            // Redirect to authorization page
            window.location.href = data.auth_url;
        } catch (error) {
            logToConsole(`Error connecting to ${selectedDestination}: ${error.message}`, 'error');
            connectDestinationBtn.textContent = 'Connect Destination';
            connectDestinationBtn.disabled = false;
        }
    });

    // Start migration button
    startMigrationBtn.addEventListener('click', async () => {
        if (!isGmailConnected || !isDestinationConnected) {
            logToConsole('Please connect both Gmail and destination accounts', 'warning');
            return;
        }

        try {
            // Get migration options
            migration.options = {
                preserveFolders: document.getElementById('preserveFolders').checked,
                includeAttachments: document.getElementById('includeAttachments').checked,
                onlyUnread: document.getElementById('onlyUnread').checked,
                startDate: document.getElementById('startDate').value || null,
                endDate: document.getElementById('endDate').value || null
            };

            logToConsole('Starting email migration...');
            startMigrationBtn.disabled = true;
            connectGmailBtn.disabled = true;
            connectDestinationBtn.disabled = true;

            // Show migration status section
            migrationStatus.classList.add('active', 'fade-in');

            // In a real app, we would make an API call to start the migration
            // For demo purposes, we'll simulate progress
            migration.status = 'running';
            migration.total = Math.floor(Math.random() * 500) + 100; // Random number of emails
            migration.processed = 0;
            migration.successful = 0;
            migration.failed = 0;
            migration.pending = migration.total;

            updateMigrationUI();

            // Simulate migration progress
            simulateMigrationProgress();
        } catch (error) {
            logToConsole(`Error starting migration: ${error.message}`, 'error');
            startMigrationBtn.disabled = false;
            connectGmailBtn.disabled = false;
            connectDestinationBtn.disabled = false;
        }
    });

    // Pause/Resume migration button
    pauseResumeMigrationBtn.addEventListener('click', () => {
        if (migration.status === 'running') {
            migration.status = 'paused';
            pauseResumeMigrationBtn.textContent = 'Resume Migration';
            logToConsole('Migration paused', 'warning');
        } else if (migration.status === 'paused') {
            migration.status = 'running';
            pauseResumeMigrationBtn.textContent = 'Pause Migration';
            logToConsole('Migration resumed', 'success');

            // Continue simulation if paused
            simulateMigrationProgress();
        }
        updateMigrationUI();
    });

    // Cancel migration button
    cancelMigrationBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to cancel the migration? This cannot be undone.')) {
            migration.status = 'cancelled';
            pauseResumeMigrationBtn.disabled = true;
            cancelMigrationBtn.disabled = true;
            downloadReportBtn.disabled = false;
            logToConsole('Migration cancelled by user', 'warning');
            updateMigrationUI();
        }
    });

    // Download report button
    downloadReportBtn.addEventListener('click', () => {
        // Generate migration report
        const report = {
            timestamp: new Date().toISOString(),
            source: 'Gmail',
            destination: selectedDestination,
            options: migration.options,
            results: {
                total: migration.total,
                processed: migration.processed,
                successful: migration.successful,
                failed: migration.failed
            },
            logs: migration.logs
        };

        // Convert report to JSON and download
        const reportBlob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const reportUrl = URL.createObjectURL(reportBlob);
        const a = document.createElement('a');
        a.href = reportUrl;
        a.download = `migration-report-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(reportUrl);

        logToConsole('Migration report downloaded', 'success');
    });

    // Update UI based on current state
    function updateUI() {
        // Start migration button
        startMigrationBtn.disabled = !(isGmailConnected && isDestinationConnected);

        // Connect destination button
        if (!isDestinationConnected) {
            connectDestinationBtn.disabled = !selectedDestination;
        }
    }

    // Update migration UI
    function updateMigrationUI() {
        // Update progress bar
        const percentage = migration.total > 0 ? Math.round((migration.processed / migration.total) * 100) : 0;
        progressBarFill.style.width = `${percentage}%`;
        processedCount.textContent = `${migration.processed}/${migration.total} emails processed`;
        progressPercentage.textContent = `${percentage}%`;

        // Update summary cards
        successCount.textContent = migration.successful;
        pendingCount.textContent = migration.pending;
        failedCount.textContent = migration.failed;

        // Update UI based on migration status
        if (migration.status === 'completed') {
            document.querySelector('.migration-status h2').textContent = 'Migration Completed';
            document.querySelector('.migration-status h2 .spinner').style.display = 'none';
            pauseResumeMigrationBtn.disabled = true;
            cancelMigrationBtn.disabled = true;
            downloadReportBtn.disabled = false;
            startMigrationBtn.disabled = false;
            connectGmailBtn.disabled = false;
            connectDestinationBtn.disabled = false;
        } else if (migration.status === 'failed') {
            document.querySelector('.migration-status h2').textContent = 'Migration Failed';
            document.querySelector('.migration-status h2 .spinner').style.display = 'none';
            pauseResumeMigrationBtn.disabled = true;
            cancelMigrationBtn.disabled = true;
            downloadReportBtn.disabled = false;
        } else if (migration.status === 'cancelled') {
            document.querySelector('.migration-status h2').textContent = 'Migration Cancelled';
            document.querySelector('.migration-status h2 .spinner').style.display = 'none';
        }
    }

    // Add log entry to both console and UI
    function logToConsole(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = { timestamp, message, type };
        migration.logs.push(logEntry);

        // Log to browser console
        switch (type) {
            case 'error':
                console.error(`${timestamp} - ${message}`);
                break;
            case 'warning':
                console.warn(`${timestamp} - ${message}`);
                break;
            case 'success':
                console.log(`%c${timestamp} - ${message}`, 'color: green');
                break;
            default:
                console.log(`${timestamp} - ${message}`);
        }

        // Add to UI log if migration status element exists
        if (migrationLog) {
            const logEntryElement = document.createElement('div');
            logEntryElement.className = `log-entry ${type}`;
            logEntryElement.textContent = `${timestamp} - ${message}`;
            migrationLog.appendChild(logEntryElement);
            migrationLog.scrollTop = migrationLog.scrollHeight;
        }
    }

    // Simulate migration progress
    async function simulateMigrationProgress() {
        if (migration.status !== 'running' || migration.processed >= migration.total) {
            return;
        }

        // Calculate how many emails to process in this batch
        const remainingEmails = migration.total - migration.processed;
        const batchSize = migration.isBatchProcessing ? Math.min(migration.batchSize, remainingEmails) : remainingEmails;

        // Simulate processing delay
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Process emails in batch
        for (let i = 0; i < batchSize && migration.status === 'running'; i++) {
            // Simulate success/failure
            const isSuccess = Math.random() > 0.1; // 90% success rate

            if (isSuccess) {
                migration.successful++;
                if (i === 0 || i === batchSize - 1 || i % Math.floor(batchSize / 3) === 0) {
                    // Log only some successful emails to avoid cluttering the log
                    logToConsole(`Successfully migrated email ${migration.processed + 1}`, 'success');
                }
            } else {
                migration.failed++;
                logToConsole(`Failed to migrate email ${migration.processed + 1}: API error`, 'error');
            }

            migration.processed++;
            migration.pending = migration.total - migration.processed;

            // Update UI more gradually for smoother appearance
            if (i % 5 === 0 || i === batchSize - 1) {
                updateMigrationUI();
            }

            // Small delay between individual emails for more realistic progress
            if (i < batchSize - 1) {
                await new Promise(resolve => setTimeout(resolve, 50));
            }
        }

        // Update UI
        updateMigrationUI();

        // If completed
        if (migration.processed >= migration.total) {
            migration.status = 'completed';
            logToConsole('Migration completed!', 'success');
            updateMigrationUI();
            return;
        }

        // Continue with next batch if still running
        if (migration.status === 'running') {
            simulateMigrationProgress();
        }
    }

    // Handle OAuth callback
    function handleOAuthCallback() {
        // Check if there are OAuth query parameters in the URL
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const provider = urlParams.get('provider') || getProviderFromPath();

        if (code && provider) {
            const storedState = localStorage.getItem(`${provider}OAuthState`);

            // If state is provided, verify it matches stored state
            if (state && storedState && state !== storedState) {
                logToConsole('OAuth state mismatch. Please try again.', 'error');
                return;
            }

            // Handle the OAuth callback for the specific provider
            processOAuthCode(provider, code);

            // Remove the query parameters from the URL
            const url = new URL(window.location.href);
            url.search = '';
            window.history.replaceState({}, document.title, url);
        }
    }

    // Get provider from URL path segment
    function getProviderFromPath() {
        const path = window.location.pathname;
        if (path.includes('/gmail/')) return 'gmail';
        if (path.includes('/outlook/')) return 'outlook';
        if (path.includes('/yahoo/')) return 'yahoo';
        return null;
    }

    // Process OAuth code for a specific provider
    async function processOAuthCode(provider, code) {
        try {
            logToConsole(`Processing ${provider} authentication...`);

            // Make request to exchange code for token
            const response = await fetch(`/${provider}/auth-callback?code=${code}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Authentication failed');
            }

            // Store the token
            localStorage.setItem(`${provider}Token`, data.access_token || data.token);

            // Update UI
            if (provider === 'gmail') {
                isGmailConnected = true;
                connectGmailBtn.textContent = 'Connected to Gmail';
                connectGmailBtn.classList.remove('primary');
                connectGmailBtn.classList.add('secondary');
            } else {
                isDestinationConnected = true;
                selectedDestination = provider;
                connectDestinationBtn.textContent = `Connected to ${provider.charAt(0).toUpperCase() + provider.slice(1)}`;
                connectDestinationBtn.classList.remove('primary');
                connectDestinationBtn.classList.add('secondary');
            }

            logToConsole(`Successfully connected to ${provider}`, 'success');
            updateUI();
        } catch (error) {
            logToConsole(`Error authenticating with ${provider}: ${error.message}`, 'error');
        }
    }

    // Check for OAuth callback when page loads
    handleOAuthCallback();

    // OAuth Settings Modal
    const oauthSettingsBtn = document.getElementById('oauthSettingsBtn');
    const oauthSettingsModal = document.getElementById('oauthSettingsModal');
    const closeModalBtn = document.querySelector('.close-modal');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    const oauthForms = {
        gmail: document.getElementById('gmailOAuthForm'),
        outlook: document.getElementById('outlookOAuthForm'),
        yahoo: document.getElementById('yahooOAuthForm')
    };

    // Open OAuth settings modal
    oauthSettingsBtn.addEventListener('click', () => {
        oauthSettingsModal.style.display = 'block';
        // Load saved OAuth settings
        loadOAuthSettings();
    });

    // Close OAuth settings modal
    closeModalBtn.addEventListener('click', () => {
        oauthSettingsModal.style.display = 'none';
    });

    // Close modal if clicked outside
    window.addEventListener('click', (event) => {
        if (event.target === oauthSettingsModal) {
            oauthSettingsModal.style.display = 'none';
        }
    });

    // Tab switching
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to current button and content
            button.classList.add('active');
            const tabName = button.getAttribute('data-tab');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });

    // Save OAuth settings
    Object.keys(oauthForms).forEach(provider => {
        oauthForms[provider].addEventListener('submit', (e) => {
            e.preventDefault();

            const formData = new FormData(oauthForms[provider]);
            const settings = {
                clientId: formData.get('clientId'),
                clientSecret: formData.get('clientSecret'),
                redirectUri: formData.get('redirectUri')
            };

            // Save to localStorage (encrypted in a real app)
            localStorage.setItem(`${provider}OAuthConfig`, JSON.stringify(settings));

            logToConsole(`${provider.charAt(0).toUpperCase() + provider.slice(1)} OAuth settings saved`, 'success');
        });
    });

    // Load OAuth settings from storage
    function loadOAuthSettings() {
        Object.keys(oauthForms).forEach(provider => {
            const savedSettings = localStorage.getItem(`${provider}OAuthConfig`);
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);

                // Fill in the form
                document.getElementById(`${provider}ClientId`).value = settings.clientId || '';
                document.getElementById(`${provider}ClientSecret`).value = settings.clientSecret || '';
                document.getElementById(`${provider}RedirectUri`).value = settings.redirectUri || '';
            }
        });
    }
});
