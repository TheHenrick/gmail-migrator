/**
 * Gmail Migrator - Main JavaScript
 */

console.log('main.js loaded');

// Global state variables
let isGmailConnected = false;
let isDestinationConnected = false;
let migrationEventSource = null;

// Function to initialize the SSE connection for migration updates
function initMigrationStatusUpdates() {
    // Close any existing connection
    if (migrationEventSource) {
        migrationEventSource.close();
        console.log('Closed existing EventSource connection');
    }

    console.log('Creating new EventSource connection to /migration/status/stream');
    // Create a new EventSource connection
    migrationEventSource = new EventSource('/migration/status/stream');

    // Handle connection open
    migrationEventSource.onopen = function() {
        console.log('Migration status stream connected successfully');
    };

    // Handle incoming messages
    migrationEventSource.onmessage = function(event) {
        console.log('Received SSE message:', event);
        try {
            console.log('Raw event data:', event.data);

            // Parse the data
            let data;
            try {
                // First try to parse as JSON directly
                data = JSON.parse(event.data);
            } catch (parseError) {
                // If that fails, try to clean the data first
                console.log('Initial JSON parse failed, cleaning data and retrying');
                const cleanData = event.data.replace(/'/g, '"')
                    .replace(/None/g, 'null')
                    .replace(/True/g, 'true')
                    .replace(/False/g, 'false');
                console.log('Cleaned data:', cleanData);
                data = JSON.parse(cleanData);
            }

            console.log('Parsed migration status update:', data);

            // Update the UI
            updateMigrationUI(data);
        } catch (error) {
            console.error('Error processing migration status update:', error, 'Raw data:', event.data);
        }
    };

    // Handle errors
    migrationEventSource.onerror = function(error) {
        console.error('Migration status stream error:', error);
        console.log('EventSource readyState:', migrationEventSource.readyState);
        // Try to reconnect after a delay
        setTimeout(() => {
            if (migrationEventSource && migrationEventSource.readyState === EventSource.CLOSED) {
                console.log('Attempting to reconnect EventSource');
                initMigrationStatusUpdates();
            }
        }, 5000);
    };
}

// Function to update the migration UI with the latest status
function updateMigrationUI(data) {
    console.log('Updating migration UI with data:', data);

    // Show the migration status section if it's hidden
    const migrationStatus = document.getElementById('migrationStatus');
    if (migrationStatus && migrationStatus.style.display === 'none') {
        migrationStatus.style.display = 'block';
    }

    // Get UI elements
    const progressBar = document.getElementById('progressBar');
    const progressPercentage = document.getElementById('progressPercentage');
    const migrationProgress = document.getElementById('migrationProgress');
    const completedCount = document.getElementById('completedCount');
    const pendingCount = document.getElementById('pendingCount');
    const failedCount = document.getElementById('failedCount');

    // Extract data with defaults
    const totalEmails = data.total_emails || 0;
    const processedEmails = data.processed_emails || 0;
    const successfulEmails = data.successful_emails || 0;
    const failedEmails = data.failed_emails || 0;
    const totalLabels = data.total_labels || 0;
    const processedLabels = data.processed_labels || 0;

    // Calculate progress percentage
    let percent = 0;
    if (totalEmails > 0) {
        percent = Math.round((processedEmails / totalEmails) * 100);
    } else if (totalLabels > 0) {
        percent = Math.round((processedLabels / totalLabels) * 100);
    }

    // Update progress bar
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
        console.log(`Updated progress bar width to ${percent}%`);
    }

    // Update progress percentage text
    if (progressPercentage) {
        progressPercentage.textContent = `${percent}%`;
        console.log(`Updated progress percentage text to ${percent}%`);
    }

    // Update emails processed text
    if (migrationProgress) {
        migrationProgress.textContent = `${processedEmails}/${totalEmails} emails processed`;
        console.log(`Updated migration progress text to ${processedEmails}/${totalEmails} emails processed`);
    }

    // Update counters
    if (completedCount) {
        completedCount.textContent = successfulEmails;
        console.log(`Updated completed count to ${successfulEmails}`);
    }

    if (failedCount) {
        failedCount.textContent = failedEmails;
        console.log(`Updated failed count to ${failedEmails}`);
    }

    if (pendingCount) {
        const pending = Math.max(0, totalEmails - processedEmails);
        pendingCount.textContent = pending;
        console.log(`Updated pending count to ${pending}`);
    }

    // Update log
    if (data.logs) {
        const migrationLog = document.getElementById('migrationLog');
        if (!migrationLog) return;

        if (typeof data.logs === 'string') {
            // Single log entry as string
            addLogEntry(data.logs, getLogType(data.logs));
        } else if (Array.isArray(data.logs)) {
            // Array of log entries
            // Clear log if it's the first update with a specific message
            if (data.logs.length === 1 && data.logs[0].includes('Starting migration process')) {
                migrationLog.innerHTML = '';
            }

            // Add new log entries
            data.logs.forEach(log => {
                if (typeof log === 'string') {
                    addLogEntry(log, getLogType(log));
                } else if (log && log.message) {
                    addLogEntry(log.message, log.type || getLogType(log.message));
                }
            });
        }
    }

    // If migration is completed, update the UI accordingly
    if (data.status === 'completed') {
        const startMigrationBtn = document.getElementById('startMigration');
        if (startMigrationBtn) {
            startMigrationBtn.disabled = false;
            startMigrationBtn.innerHTML = '<i class="fas fa-check"></i> Migration Complete';
            startMigrationBtn.classList.remove('button-pressed');
        }
    }
}

// Function to refresh tokens before migration
async function refreshTokensBeforeMigration() {
    console.log('Refreshing tokens before migration');

    // Check if tokens exist
    const gmailToken = localStorage.getItem('gmailToken');
    const outlookToken = localStorage.getItem('outlookToken');

    if (!gmailToken) {
        throw new Error('Gmail token not found. Please connect your Gmail account.');
    }

    if (!outlookToken) {
        throw new Error('Outlook token not found. Please connect your Outlook account.');
    }

    // Try to refresh Gmail token if we have a refresh token
    const gmailRefreshToken = localStorage.getItem('gmailRefreshToken');
    if (gmailRefreshToken) {
        try {
            const response = await fetch('/gmail/refresh-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ refresh_token: gmailRefreshToken })
            });

            if (response.ok) {
                const data = await response.json();
                if (data.access_token) {
                    localStorage.setItem('gmailToken', data.access_token);
                    console.log('Gmail token refreshed successfully');
                }
            } else {
                console.warn('Failed to refresh Gmail token:', await response.text());
            }
        } catch (error) {
            console.warn('Error refreshing Gmail token:', error);
        }
    }

    // Try to refresh Outlook token
    try {
        const response = await fetch('/outlook/refresh-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: outlookToken })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.access_token) {
                localStorage.setItem('outlookToken', data.access_token);
                console.log('Outlook token refreshed successfully');
            }
        } else {
            console.warn('Failed to refresh Outlook token:', await response.text());
        }
    } catch (error) {
        console.warn('Error refreshing Outlook token:', error);
    }

    // Return the latest tokens
    return {
        gmailToken: localStorage.getItem('gmailToken'),
        outlookToken: localStorage.getItem('outlookToken')
    };
}

// Define the migration implementation function
window.performMigration = async function() {
    try {
        console.log('Starting migration process');

        // Initialize the SSE connection for status updates
        initMigrationStatusUpdates();

        // Show loading state
        const startMigrationBtn = document.getElementById('startMigration');
        if (startMigrationBtn) {
            startMigrationBtn.disabled = true;
            startMigrationBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Migrating...';
            startMigrationBtn.classList.add('button-pressed');
        }

        // Show the migration status section
        const migrationStatus = document.getElementById('migrationStatus');
        if (migrationStatus) {
            migrationStatus.style.display = 'block';
        }

        // Clear the migration log
        const migrationLog = document.getElementById('migrationLog');
        if (migrationLog) {
            migrationLog.innerHTML = '';
        }

        // Get the selected destination
        const destinationSelect = document.getElementById('destinationSelect');
        const destination = destinationSelect ? destinationSelect.value : 'outlook';
        console.log('Selected destination:', destination);

        // Remove any existing error messages
        const existingErrors = document.querySelectorAll('.alert.alert-danger');
        existingErrors.forEach(error => error.remove());

        if (destination === 'outlook') {
            // First refresh tokens
            try {
                const tokens = await refreshTokensBeforeMigration();
                console.log('Tokens refreshed, proceeding with migration');

                // Get the tokens from localStorage (now refreshed)
                const gmailToken = tokens.gmailToken;
                const gmailRefreshToken = localStorage.getItem('gmailRefreshToken');
                const outlookToken = tokens.outlookToken;

                // Log the tokens (partially masked for security)
                console.log('Gmail token:', gmailToken.substring(0, 10) + '...');
                console.log('Gmail refresh token:', gmailRefreshToken ? gmailRefreshToken.substring(0, 10) + '...' : 'Not available');
                console.log('Outlook token:', outlookToken.substring(0, 10) + '...');

                // Prepare the credentials object in the format expected by the server
                const gmailCredentials = {
                    token: gmailToken,
                    refresh_token: gmailRefreshToken || '',
                    client_id: document.querySelector('meta[name="google-signin-client_id"]')?.content || '',
                    client_secret: '',
                    token_uri: 'https://oauth2.googleapis.com/token'
                };

                // Prepare the credentials request body
                const credentialsRequestBody = {
                    credentials: {
                        gmail: gmailCredentials,
                        destination: {
                            token: outlookToken,
                            provider: 'outlook'
                        }
                    }
                };

                // First migrate labels to folders
                logToConsole('Migrating Gmail labels to Outlook folders...', 'info');
                console.log('Sending request to /migration/gmail-to-outlook/labels');

                // Use Promise-based approach for better readability
                fetch('/migration/gmail-to-outlook/labels', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(credentialsRequestBody)
                })
                .then(response => {
                    console.log('Labels response status:', response.status);
                    if (!response.ok) {
                        // Handle authentication errors
                        if (response.status === 401) {
                            return response.text().then(text => {
                                console.error('Authentication error:', text);
                                logToConsole('Authentication failed. Please reconnect your accounts.', 'error');

                                // Show error message to the user
                                const errorElement = document.createElement('div');
                                errorElement.className = 'alert alert-danger';
                                errorElement.textContent = 'Migration Failed: Failed to migrate labels: Unauthorized';

                                // Insert the error message at the top of the page
                                const container = document.querySelector('.container') || document.body;
                                container.insertBefore(errorElement, container.firstChild);

                                // Reset the migration button
                                resetMigrationButton();

                                // Force reset all authentication state and UI
                                forceResetAuthState();

                                throw new Error('Authentication failed. Please reconnect your accounts.');
                            });
                        }
                        throw new Error(`Failed to migrate labels: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(labelsResult => {
                    logToConsole(`Successfully migrated ${Object.keys(labelsResult).length} labels to folders`, 'success');

                    // Then migrate all emails
                    logToConsole('Migrating all emails...', 'info');

                    // Prepare the full migration request body
                    const fullMigrationRequestBody = {
                        max_emails_per_label: 100,
                        credentials: {
                            gmail: gmailCredentials,
                            destination: {
                                token: outlookToken,
                                provider: 'outlook'
                            }
                        }
                    };

                    return fetch('/migration/gmail-to-outlook/all', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(fullMigrationRequestBody)
                    });
                })
                .then(response => {
                    console.log('Migration response status:', response.status);
                    if (!response.ok) {
                        throw new Error(`Failed to migrate emails: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(migrationResult => {
                    console.log('Migration result:', migrationResult);

                    // Log the results
                    const successCount = migrationResult.successful || 0;
                    const totalCount = migrationResult.total || 0;
                    const failedCount = migrationResult.failed || 0;

                    logToConsole(`Migration complete: ${successCount} of ${totalCount} emails migrated successfully`, 'success');

                    if (failedCount > 0) {
                        logToConsole(`[WARNING] ${failedCount} emails failed to migrate`, 'warning');
                    }

                    // The UI will be updated by the SSE connection
                })
                .catch(error => {
                    console.error('Migration error:', error);
                    logToConsole(`Migration error: ${error.message}`, 'error');

                    // Show error message to the user
                    const errorElement = document.createElement('div');
                    errorElement.className = 'alert alert-danger';
                    errorElement.textContent = `Migration Failed: ${error.message}`;

                    // Insert the error message at the top of the page
                    const container = document.querySelector('.container') || document.body;
                    container.insertBefore(errorElement, container.firstChild);

                    // Update button state
                    resetMigrationButton();

                    // Check if it's an authentication error
                    if (error.message.includes('authentication') ||
                        error.message.includes('Authentication') ||
                        error.message.includes('Unauthorized') ||
                        error.message.includes('unauthorized') ||
                        error.message.includes('token') ||
                        error.message.includes('credentials')) {

                        console.log('Authentication-related error detected, resetting connections');
                        // Force reset all authentication state and UI
                        forceResetAuthState();
                    }

                    // Close the event source
                    if (migrationEventSource) {
                        migrationEventSource.close();
                        migrationEventSource = null;
                    }
                });
            } catch (error) {
                console.error('Token refresh error:', error);
                logToConsole(`Token refresh error: ${error.message}`, 'error');

                // Show error message to the user
                const errorElement = document.createElement('div');
                errorElement.className = 'alert alert-danger';
                errorElement.textContent = `Migration Failed: Token refresh error - ${error.message}`;

                // Insert the error message at the top of the page
                const container = document.querySelector('.container') || document.body;
                container.insertBefore(errorElement, container.firstChild);

                // Reset the migration button
                resetMigrationButton();

                // Force reset all authentication state and UI
                forceResetAuthState();
            }
        } else {
            logToConsole(`Migration to ${destination} is not implemented yet`, 'warning');
            resetMigrationButton();
        }
    } catch (error) {
        console.error('Migration error:', error);
        logToConsole(`Error during migration: ${error.message}`, 'error');
        resetMigrationButton();
    }
};

// Define the full migration function immediately
console.log('Defining startMigration function in main.js');
window.startMigration = function() {
    console.log('%c MIGRATION STARTED FROM MAIN.JS! ', 'background: #4CAF50; color: white; font-size: 16px; padding: 5px;');
    logToConsole('Starting migration process...', 'info');

    try {
        // Show loading state
        const startMigrationBtn = document.getElementById('startMigration');
        if (startMigrationBtn) {
            startMigrationBtn.disabled = true;
            startMigrationBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Migrating...';
            startMigrationBtn.classList.add('button-pressed');
        }

        // Get the selected destination
        const destinationSelect = document.getElementById('destinationSelect');
        const destination = destinationSelect ? destinationSelect.value : 'outlook';
        console.log('Selected destination:', destination);

        if (destination === 'outlook') {
            // First migrate labels to folders
            logToConsole('Migrating Gmail labels to Outlook folders...', 'info');
            console.log('Sending request to /migration/gmail-to-outlook/labels');

            // Use Promise-based approach for better readability
            fetch('/migration/gmail-to-outlook/labels', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('gmailToken')}`
                }
            })
            .then(response => {
                console.log('Labels response status:', response.status);
                if (!response.ok) {
                    throw new Error(`Failed to migrate labels: ${response.statusText}`);
                }
                return response.json();
            })
            .then(labelsResult => {
                logToConsole(`Successfully migrated ${Object.keys(labelsResult).length} labels to folders`, 'success');

                // Then migrate all emails
                logToConsole('Migrating all emails...', 'info');
                return fetch('/migration/gmail-to-outlook/all', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('gmailToken')}`
                    },
                    body: JSON.stringify({
                        max_emails_per_label: 100
                    })
                });
            })
            .then(response => {
                console.log('Migration response status:', response.status);
                if (!response.ok) {
                    throw new Error(`Failed to migrate emails: ${response.statusText}`);
                }
                return response.json();
            })
            .then(migrationResult => {
                console.log('Migration result:', migrationResult);

                // Log the results
                const successCount = migrationResult.successful || 0;
                const totalCount = migrationResult.total || 0;
                const failedCount = migrationResult.failed || 0;

                logToConsole(`Migration complete: ${successCount} of ${totalCount} emails migrated successfully`, 'success');

                if (failedCount > 0) {
                    logToConsole(`[WARNING] ${failedCount} emails failed to migrate`, 'warning');
                }

                // The UI will be updated by the SSE connection
            })
            .catch(error => {
                console.error('Migration error:', error);
                logToConsole(`Migration error: ${error.message}`, 'error');

                // Update button state
                const startMigrationBtn = document.getElementById('startMigration');
                if (startMigrationBtn) {
                    startMigrationBtn.disabled = false;
                    startMigrationBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Migration Failed';
                    startMigrationBtn.classList.remove('button-pressed');
                }

                // Close the event source
                if (migrationEventSource) {
                    migrationEventSource.close();
                    migrationEventSource = null;
                }
            });
        } else {
            logToConsole(`Migration to ${destination} is not yet implemented`, 'warning');
            resetMigrationButton();
        }
    } catch (error) {
        console.error('Migration error:', error);
        logToConsole(`Error during migration: ${error.message}`, 'error');
        resetMigrationButton();
    }
};

// Make connectToGmail function globally available
window.connectToGmail = async function() {
    console.log('Global connectToGmail function called');
    console.trace('Stacktrace for connectToGmail call'); // Add stack trace to identify caller

    // First check if user is already authenticated
    const gmailToken = localStorage.getItem('gmailToken');
    if (gmailToken) {
        console.log('User already has a token, not starting OAuth flow');
        return; // Prevent OAuth flow if already signed in
    }

    try {
        logToConsole('Initiating direct Gmail OAuth flow...', 'info');

        // Skip the Google Sign-In popup and go directly to OAuth
        const authUrl = await getGmailOAuthUrl();
        console.log('Got auth URL:', authUrl);
        if (authUrl) {
            logToConsole('Redirecting to Gmail OAuth...', 'info');
            window.location.href = authUrl;
        } else {
            throw new Error('Failed to get OAuth URL');
        }
    } catch (error) {
        console.error('Error in connectToGmail:', error);
        logToConsole(`Error connecting to Gmail: ${error.message}`, 'error');
    }
};

// Function to log messages to the console and migration log
function logToConsole(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);

    // Add to migration log if it exists
    const migrationLog = document.getElementById('migrationLog');
    if (migrationLog) {
        const logEntry = document.createElement('div');
        logEntry.className = type;

        const timestamp = document.createElement('span');
        timestamp.className = 'timestamp';
        timestamp.textContent = new Date().toLocaleTimeString() + ' ';

        const messageSpan = document.createElement('span');
        messageSpan.className = 'message';
        messageSpan.textContent = message;

        logEntry.appendChild(timestamp);
        logEntry.appendChild(messageSpan);
        migrationLog.appendChild(logEntry);

        // Scroll to bottom
        migrationLog.scrollTop = migrationLog.scrollHeight;
    }
}

// Function to handle Google Sign-In response
function handleGoogleSignIn(response) {
    logToConsole('Google Sign-In response received', 'info');

    if (response && response.credential) {
        logToConsole('Credential received, exchanging for access token', 'info');

        // Exchange the credential for an access token
        exchangeGoogleCredential(response.credential)
            .then(success => {
                if (success) {
                    logToConsole('Successfully connected to Gmail', 'success');
                    updateUIAfterGmailConnection(true);
                } else {
                    logToConsole('Failed to connect to Gmail', 'error');
                    updateUIAfterGmailConnection(false);
                }
            })
            .catch(error => {
                logToConsole('Error exchanging credential: ' + error, 'error');
                updateUIAfterGmailConnection(false);
            });
    } else {
        logToConsole('No credential in response', 'error');
        updateUIAfterGmailConnection(false);
    }
}

// Function to parse JWT token
function parseJwt(token) {
    try {
        // Get the payload part of the JWT
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));

        return JSON.parse(jsonPayload);
    } catch (error) {
        logToConsole('Error parsing JWT: ' + error.message, 'error');
        return null;
    }
}

// Function to exchange Google credential for Gmail access
async function exchangeGoogleCredential(credential) {
    logToConsole('Exchanging Google credential for Gmail access token', 'info');

    try {
        // Extract user info from the credential
        try {
            const payload = parseJwt(credential);
            localStorage.setItem('gmailUserInfo', JSON.stringify({
                name: payload.name,
                email: payload.email,
                picture: payload.picture
            }));
            logToConsole('User info stored: ' + payload.name + ' (' + payload.email + ')', 'info');
        } catch (error) {
            logToConsole('Error parsing JWT: ' + error, 'error');
        }

        // Exchange the credential with our backend
        const response = await fetch('/gmail/exchange-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ credential })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server responded with ${response.status}: ${errorText}`);
        }

        const data = await response.json();

        if (data.access_token) {
            logToConsole('Received access token from server', 'success');
            localStorage.setItem('gmailToken', data.access_token);

            // Store refresh token if available
            if (data.refresh_token) {
                localStorage.setItem('gmailRefreshToken', data.refresh_token);
                logToConsole('Refresh token stored', 'success');
            } else {
                logToConsole('No refresh token received from server', 'warning');
            }

            // Store client credentials if available
            if (data.client_id) {
                localStorage.setItem('gmailClientId', data.client_id);
                logToConsole('Client ID stored', 'success');
            }

            if (data.client_secret) {
                localStorage.setItem('gmailClientSecret', data.client_secret);
                logToConsole('Client secret stored', 'success');
            }

            // Update UI to show connected state
            updateUIAfterGmailConnection(true);
            return true;
        } else {
            logToConsole('No access token received from server', 'error');
            updateUIAfterGmailConnection(false);
            return false;
        }
    } catch (error) {
        logToConsole('Error exchanging credential: ' + error.message, 'error');
        updateUIAfterGmailConnection(false);
        return false;
    }
}

// Function to update UI after Gmail connection attempt
function updateUIAfterGmailConnection(success) {
    if (success) {
        // Update the Gmail auth button
        updateGmailAuthButton();

        // Enable destination buttons
        const outlookAuthBtn = document.getElementById('outlookAuthBtn');
        const yahooAuthBtn = document.getElementById('yahooAuthBtn');

        if (outlookAuthBtn) outlookAuthBtn.disabled = false;
        if (yahooAuthBtn) yahooAuthBtn.disabled = false;

        // Show destination options
        showDestinationOptions();

        // Update state
        isGmailConnected = true;
    } else {
        console.log('Gmail connection failed, resetting UI state');

        // Show error message
        const gmailAuthContainer = document.getElementById('googleSignInButtonContainer');
        if (gmailAuthContainer) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = 'Failed to connect to Gmail. Please try again.';
            gmailAuthContainer.appendChild(errorMessage);
        }

        // Clear any stored tokens
        localStorage.removeItem('gmailToken');
        localStorage.removeItem('gmailRefreshToken');
        localStorage.removeItem('gmailUserInfo');

        // Update the Gmail auth button
        updateGmailAuthButton();

        // Update global state
        isGmailConnected = false;

        // Force a page reload after a short delay to ensure UI is fully reset
        setTimeout(() => {
            window.location.reload();
        }, 2000);
    }
}

// Function to update the Gmail auth button based on authentication state
function updateGmailAuthButton() {
    logToConsole('Updating Gmail auth button', 'info');
    const gmailAuthContainer = document.getElementById('googleSignInButtonContainer');

    if (!gmailAuthContainer) {
        logToConsole('Gmail auth container not found', 'error');
        return;
    }

    // Clear any existing content in the container
    gmailAuthContainer.innerHTML = '';

    // Check if we have a Gmail token
    const gmailToken = localStorage.getItem('gmailToken');
    const userInfoStr = localStorage.getItem('gmailUserInfo');

    if (gmailToken && userInfoStr) {
        try {
            const userInfo = JSON.parse(userInfoStr);
            logToConsole('User info found: ' + JSON.stringify(userInfo), 'info');

            // Create a custom button that matches Microsoft and Yahoo buttons
            const button = document.createElement('button');
            button.className = 'google-auth-button'; // Use our new dedicated class

            // Create the button content
            button.innerHTML = `
                <img src="/static/img/google-logo.svg" alt="Google Logo" class="auth-button-icon">
                <span style="flex: 1;">${userInfo.email}</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#5f6368" class="logout-icon">
                    <path d="M5 5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7v-2H5V5zm16 7l-4-4v3H9v2h8v3l4-4z"></path>
                </svg>
            `;

            // Add click event to disconnect
            button.addEventListener('click', disconnectGmail);

            // Add the button to the container
            gmailAuthContainer.appendChild(button);

            // Enable the destination connection buttons
            const outlookAuthBtn = document.getElementById('outlookAuthBtn');
            const yahooAuthBtn = document.getElementById('yahooAuthBtn');

            if (outlookAuthBtn) outlookAuthBtn.disabled = false;
            if (yahooAuthBtn) yahooAuthBtn.disabled = false;

            // Update state
            isGmailConnected = true;

            // Show destination options
            showDestinationOptions();

        } catch (error) {
            logToConsole('Error parsing user info: ' + error, 'error');
            disconnectGmail();
        }
    } else {
        // Not connected, create a new Google Sign-In button that matches other buttons
        const button = document.createElement('button');
        button.className = 'google-auth-button'; // Use our new dedicated class

        // Create the button content
        button.innerHTML = `
            <img src="/static/img/google-logo.svg" alt="Google Logo" class="auth-button-icon">
            <span>Sign in with Google</span>
        `;

        // Add click event to initiate Google sign-in
        button.addEventListener('click', async function() {
            const url = await getGmailOAuthUrl();
            if (url) {
                window.location.href = url;
            }
        });

        // Add the button to the container
        gmailAuthContainer.appendChild(button);
    }
}

// Function to disconnect from Gmail
function disconnectGmail() {
    console.log('Disconnecting Gmail account...');

    // Clear Gmail tokens from localStorage
    localStorage.removeItem('gmailToken');
    localStorage.removeItem('gmailRefreshToken');
    localStorage.removeItem('gmailUserInfo');

    // Update UI to show disconnected state
    const gmailConnectBtn = document.getElementById('gmailConnectBtn');
    const gmailConnectedInfo = document.getElementById('gmailConnectedInfo');

    if (gmailConnectBtn) gmailConnectBtn.style.display = 'block';
    if (gmailConnectedInfo) gmailConnectedInfo.style.display = 'none';

    // Update global state
    isGmailConnected = false;

    // Update migration button state
    updateMigrationButtonState();

    // Add a log entry
    logToConsole('Gmail account disconnected. Please reconnect to continue.', 'warning');

    // Reload the page to ensure all UI elements are reset
    setTimeout(() => {
        window.location.reload();
    }, 2000);
}

// Function to get Gmail OAuth URL
async function getGmailOAuthUrl() {
    console.log('getGmailOAuthUrl function called');
    try {
        console.log('Fetching OAuth URL from server...');
        const response = await fetch('/gmail/auth-url', {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            }
        });

        console.log('OAuth URL response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('OAuth URL error response:', errorText);
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        console.log('OAuth URL response data:', data);
        return data.auth_url;
    } catch (error) {
        console.error('Error getting Gmail OAuth URL:', error);
        logToConsole(`Error getting Gmail OAuth URL: ${error.message}`, 'error');
        return null;
    }
}

// Function to show destination options
function showDestinationOptions() {
    console.log('showDestinationOptions called');

    // This function is no longer needed since we're using direct buttons
    // Just log a message and return
    logToConsole('Destination options are now directly available', 'info');

    // Enable destination buttons if Gmail is connected
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');

    if (outlookAuthBtn) outlookAuthBtn.disabled = false;
    if (yahooAuthBtn) yahooAuthBtn.disabled = false;
}

// Function to initialize the application
function initializeApp() {
    console.log('Initializing application...');

    // Initialize Google Sign-In
    initializeGoogleSignIn();

    // Handle OAuth callback if present
    handleOAuthCallback();

    // Initialize destination selection
    initializeDestinationSelection();

    // Initialize advanced options toggle
    initializeAdvancedOptionsToggle();

    // Initialize batch size slider
    initializeBatchSizeSlider();

    // Initialize migration options
    initializeMigrationOptions();

    // Initialize OAuth settings modal
    initializeOAuthSettingsModal();

    // Initialize tooltips
    createMD3Tooltip();

    // Initialize download report button
    const downloadReportBtn = document.getElementById('downloadReport');
    if (downloadReportBtn) {
        downloadReportBtn.addEventListener('click', handleDownloadReport);
    }

    // Initialize pause/resume and cancel buttons
    const pauseResumeBtn = document.getElementById('pauseResumeMigration');
    const cancelBtn = document.getElementById('cancelMigration');

    if (pauseResumeBtn) {
        pauseResumeBtn.addEventListener('click', function() {
            // This would be implemented when we add pause/resume functionality
            alert('Pause/Resume functionality will be implemented in a future update.');
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            // This would be implemented when we add cancel functionality
            if (confirm('Are you sure you want to cancel the migration?')) {
                const migrationStatus = document.getElementById('migrationStatus');
                if (migrationStatus) {
                    migrationStatus.style.display = 'none';
                }
                resetMigrationButton();
            }
        });
    }

    // Animate UI elements
    animateUIElements();

    console.log('Application initialized successfully');
}

// Function to animate UI elements
function animateUIElements() {
    console.log("Animating UI elements");

    // Add visible class to advanced options if they were previously open
    const advancedOptionsVisible = localStorage.getItem('advancedOptionsVisible') === 'true';
    if (advancedOptionsVisible) {
        document.getElementById('advancedOptions').classList.add('visible');
        document.getElementById('advancedOptionsToggle').classList.add('active');
    }

    // Only fade in option items without any movement
    const optionItems = document.querySelectorAll('.option-item');
    optionItems.forEach((item, index) => {
        setTimeout(() => {
            item.style.opacity = '0';
            item.style.transition = 'opacity 0.5s ease';

            setTimeout(() => {
                item.style.opacity = '1';
            }, 50);
        }, index * 100);
    });

    // Only fade in options row without any movement
    const optionsRow = document.querySelector('.options-row');
    if (optionsRow) {
        optionsRow.style.opacity = '0';
        optionsRow.style.transition = 'opacity 0.5s ease';

        setTimeout(() => {
            optionsRow.style.opacity = '1';
        }, 100);
    }

    // No animations for auth sections row
}

// Function to initialize advanced options toggle
function initializeAdvancedOptionsToggle() {
    const advancedOptionsToggle = document.getElementById('advancedOptionsToggle');
    const advancedOptions = document.getElementById('advancedOptions');

    if (advancedOptionsToggle && advancedOptions) {
        advancedOptionsToggle.addEventListener('click', function() {
            advancedOptionsToggle.classList.toggle('active');
            advancedOptions.classList.toggle('visible');

            // Store the state in localStorage
            localStorage.setItem('advancedOptionsOpen', advancedOptions.classList.contains('visible'));
        });

        // Check if advanced options were previously open
        if (localStorage.getItem('advancedOptionsOpen') === 'true') {
            advancedOptionsToggle.classList.add('active');
            advancedOptions.classList.add('visible');
        }
    }
}

// Function to initialize batch size slider
function initializeBatchSizeSlider() {
    const batchSizeSlider = document.getElementById('batchSizeSlider');
    const batchSizeValue = document.getElementById('batchSizeValue');
    const batchProcessingCheckbox = document.getElementById('batchProcessing');
    const batchSizeContainer = document.getElementById('batchSizeContainer');

    if (batchSizeSlider && batchSizeValue) {
        batchSizeSlider.addEventListener('input', function() {
            batchSizeValue.textContent = `${this.value} emails`;
        });
    }

    if (batchProcessingCheckbox && batchSizeContainer) {
        // Show/hide batch size slider based on checkbox
        batchProcessingCheckbox.addEventListener('change', function() {
            if (this.checked) {
                batchSizeContainer.style.maxHeight = '100px';
                batchSizeContainer.style.opacity = '1';
                batchSizeContainer.style.marginBottom = 'var(--spacing-large)';
                batchSizeContainer.style.padding = 'var(--spacing-medium)';
            } else {
                batchSizeContainer.style.maxHeight = '0';
                batchSizeContainer.style.opacity = '0';
                batchSizeContainer.style.marginBottom = '0';
                batchSizeContainer.style.padding = '0';
            }
        });

        // Initialize state
        if (!batchProcessingCheckbox.checked) {
            batchSizeContainer.style.maxHeight = '0';
            batchSizeContainer.style.opacity = '0';
            batchSizeContainer.style.marginBottom = '0';
            batchSizeContainer.style.padding = '0';
        }
    }
}

// Function to initialize migration options
function initializeMigrationOptions() {
    // Add ripple effect to buttons
    const buttons = document.querySelectorAll('.button');
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const ripple = document.createElement('span');
            ripple.classList.add('ripple');
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;

            button.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
}

// Function to initialize Google Sign-In
function initializeGoogleSignIn() {
    console.log('Initializing Google Sign-In...');

    // Check if Gmail token exists in localStorage
    const gmailToken = localStorage.getItem('gmailToken');
    if (gmailToken) {
        // User is already authenticated, update UI
        updateUIAfterGmailConnection(true);
    } else {
        // User is not authenticated, show connect button
        updateUIAfterGmailConnection(false);
    }
}

// Function to handle OAuth callback parameters from URL
function handleOAuthCallback() {
    console.log('Checking for OAuth callback parameters');

    // Get URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');
    const error = urlParams.get('error');
    const outlookAuth = urlParams.get('outlook_auth');
    const token = urlParams.get('token');
    const refreshToken = urlParams.get('refresh_token');
    const email = urlParams.get('email');

    console.log('URL parameters:', {
        code: code ? `${code.substring(0, 10)}...` : null,
        state,
        error,
        outlookAuth,
        token: token ? `${token.substring(0, 10)}...` : null,
        refreshToken: refreshToken ? `${refreshToken.substring(0, 10)}...` : null,
        email
    });

    // Clean up URL - remove parameters to prevent reprocessing on refresh
    if (history.pushState && (code || state || error || outlookAuth || token)) {
        const newurl = window.location.protocol + '//' + window.location.host + window.location.pathname;
        window.history.pushState({path: newurl}, '', newurl);
        console.log('Cleaned up URL parameters');
    }

    // Handle Outlook auth success from redirect
    if (outlookAuth === 'success' && token) {
        logToConsole('Successfully connected to Outlook', 'success');
        localStorage.setItem('outlookToken', token);

        if (refreshToken) {
            localStorage.setItem('outlookRefreshToken', refreshToken);
        }

        if (email) {
            console.log('Storing Outlook email:', email);
            localStorage.setItem('outlookUserEmail', decodeURIComponent(email));
            logToConsole(`Connected as ${decodeURIComponent(email)}`, 'info');
        } else {
            console.warn('No email provided in the redirect URL');
            localStorage.setItem('outlookUserEmail', 'Microsoft Account');
        }

        updateUIAfterOutlookConnection(true);
        return;
    }

    // Handle Outlook auth error from redirect
    if (error && error.includes('outlook_auth_failed')) {
        const message = urlParams.get('message') || 'Unknown error';
        logToConsole(`Error connecting to Outlook: ${message}`, 'error');
        updateUIAfterOutlookConnection(false);
        return;
    }

    // If we have code or state, we might be in a callback
    if (code || state || error) {
        console.log('Found OAuth callback parameters in URL');
        logToConsole('Processing OAuth callback...', 'info');

        // Check for error
        if (error) {
            logToConsole(`OAuth error: ${error}`, 'error');
            return;
        }

        // Determine which provider this is for based on the current path
        const path = window.location.pathname;

        if (path.includes('/gmail/auth-callback') && code) {
            // Handle Gmail callback - already implemented
        } else if (path.includes('/yahoo/auth-callback') && code) {
            // Handle Yahoo callback - to be implemented
        }
    } else {
        console.log('No OAuth callback parameters found in URL');
    }
}

// Function to initialize destination selection
function initializeDestinationSelection() {
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');

    // Check if we have stored tokens
    const outlookToken = localStorage.getItem('outlookToken');
    const outlookUserEmail = localStorage.getItem('outlookUserEmail');
    const yahooToken = localStorage.getItem('yahooToken');
    const yahooUserEmail = localStorage.getItem('yahooUserEmail');

    // Set up Outlook button
    if (outlookAuthBtn) {
        if (outlookToken && outlookUserEmail) {
            // Already connected to Outlook
            outlookAuthBtn.classList.add('connected');
            outlookAuthBtn.innerHTML = `
                <img src="/static/img/microsoft-logo.svg" alt="Microsoft Logo" class="auth-button-icon">
                <span style="flex: 1;">${outlookUserEmail}</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#5f6368" class="logout-icon">
                    <path d="M5 5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7v-2H5V5zm16 7l-4-4v3H9v2h8v3l4-4z"></path>
                </svg>
            `;
            outlookAuthBtn.removeEventListener('click', connectToOutlook);
            outlookAuthBtn.addEventListener('click', disconnectOutlook);

            // Hide Yahoo button if connected to Outlook
            if (yahooAuthBtn) {
                yahooAuthBtn.style.display = 'none';
            }

            isDestinationConnected = true;
            updateStartButtonState();
        } else {
            // Not connected to Outlook
            outlookAuthBtn.addEventListener('click', function(e) {
                e.preventDefault();
                localStorage.setItem('selectedDestinationProvider', 'outlook');
                connectToOutlook();
            });
        }
    }

    // Set up Yahoo button
    if (yahooAuthBtn) {
        if (yahooToken && yahooUserEmail) {
            // Already connected to Yahoo
            yahooAuthBtn.classList.add('connected');
            yahooAuthBtn.innerHTML = `
                <img src="/static/img/yahoo-white-icon.svg" alt="Yahoo Logo" class="auth-button-icon">
                <span style="flex: 1;">${yahooUserEmail}</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#ffffff" class="logout-icon">
                    <path d="M5 5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7v-2H5V5zm16 7l-4-4v3H9v2h8v3l4-4z"></path>
                </svg>
            `;
            yahooAuthBtn.removeEventListener('click', connectToYahoo);
            yahooAuthBtn.addEventListener('click', disconnectYahoo);

            // Hide Outlook button if connected to Yahoo
            if (outlookAuthBtn) {
                outlookAuthBtn.style.display = 'none';
            }

            isDestinationConnected = true;
            updateStartButtonState();
        } else {
            // Not connected to Yahoo
            yahooAuthBtn.addEventListener('click', function(e) {
                e.preventDefault();
                localStorage.setItem('selectedDestinationProvider', 'yahoo');
                connectToYahoo();
            });
        }
    }
}

function updateStartButtonTooltip() {
    const startMigrationBtn = document.getElementById('startMigration');
    if (!startMigrationBtn) return;

    let tooltipText = '';

    if (!isGmailConnected && !isDestinationConnected) {
        tooltipText = 'Connect both accounts to begin';
    } else if (!isGmailConnected) {
        tooltipText = 'Connect a Gmail account to continue';
    } else if (!isDestinationConnected) {
        tooltipText = 'Connect a destination account to continue';
    } else {
        // Both are connected, show a ready message
        tooltipText = 'Ready to migrate your emails';
    }

    // Set the data-tooltip attribute
    startMigrationBtn.setAttribute('data-tooltip', tooltipText);

    // Update the MD3 tooltip text
    updateMD3TooltipText();

    // Log the tooltip update
    console.log('Updated start button tooltip:', tooltipText);
}

/**
 * Creates the tooltip element for the start migration button styled with Apple HIG
 */
function createMD3Tooltip() {
    const startMigrationBtn = document.getElementById('startMigration');
    if (!startMigrationBtn) {
        console.error('Start migration button not found');
        return;
    }

    console.log('Creating Apple HIG tooltip for start migration button');

    // Remove any existing tooltip
    const existingTooltip = document.getElementById('startMigrationTooltip');
    if (existingTooltip) {
        existingTooltip.remove();
    }

    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.className = 'md3-tooltip';
    tooltip.id = 'startMigrationTooltip';

    // Get tooltip text from button
    const tooltipText = startMigrationBtn.getAttribute('data-tooltip') || 'Connect accounts to start migration';
    tooltip.textContent = tooltipText;

    // Append tooltip to the document body
    document.body.appendChild(tooltip);

    // Track if mouse is over the button
    let isMouseOverButton = false;

    // Add event listeners for tooltip - Apple HIG style interactions
    startMigrationBtn.addEventListener('mouseenter', function(event) {
        isMouseOverButton = true;
        // Apple typically shows tooltips after a very short delay
        setTimeout(() => {
            if (isMouseOverButton) {
                showMD3Tooltip(event);
            }
        }, 50);
    });

    startMigrationBtn.addEventListener('mouseleave', function() {
        isMouseOverButton = false;
        hideMD3Tooltip();
    });

    startMigrationBtn.addEventListener('focus', function(event) {
        // Show tooltip immediately on focus (accessibility)
        showMD3Tooltip(event);
    });

    startMigrationBtn.addEventListener('blur', hideMD3Tooltip);

    // Add event listener to keep tooltip visible when mouse moves over the button
    startMigrationBtn.addEventListener('mousemove', function(event) {
        if (isMouseOverButton) {
            // Ensure tooltip is visible
            const tooltip = document.getElementById('startMigrationTooltip');
            if (tooltip && !tooltip.classList.contains('visible')) {
                showMD3Tooltip(event);
            }
        }
    });

    // Log that tooltip was created
    console.log('Apple HIG tooltip created with text:', tooltipText);

    // Initially position the tooltip but keep it hidden
    // This helps with initial positioning calculations
    tooltip.style.visibility = 'hidden';
    tooltip.style.opacity = '0';

    const buttonRect = startMigrationBtn.getBoundingClientRect();
    tooltip.style.position = 'absolute';
    tooltip.style.top = `${buttonRect.top - 40}px`;
    tooltip.style.left = `${buttonRect.left + (buttonRect.width / 2)}px`;
    tooltip.style.transform = 'translateX(-50%)';
}

/**
 * Shows the Material Design 3 tooltip styled with Apple HIG
 */
function showMD3Tooltip(event) {
    const startMigrationBtn = document.getElementById('startMigration');
    const tooltip = document.getElementById('startMigrationTooltip');

    if (!startMigrationBtn || !tooltip) return;

    // If tooltip is already visible, don't reposition it
    if (tooltip.classList.contains('visible')) {
        return;
    }

    // Update tooltip text
    tooltip.textContent = startMigrationBtn.getAttribute('data-tooltip') || 'Connect accounts to start migration';

    // First set tooltip to visible but with opacity 0 to calculate its dimensions
    tooltip.style.visibility = 'visible';
    tooltip.style.opacity = '0';

    // Position the tooltip above the button
    const buttonRect = startMigrationBtn.getBoundingClientRect();

    // Wait for the browser to calculate the tooltip dimensions
    setTimeout(() => {
        const tooltipRect = tooltip.getBoundingClientRect();

        // Calculate position - Apple HIG typically positions tooltips with more space
        const top = buttonRect.top + window.scrollY - tooltipRect.height - 16;
        const left = buttonRect.left + window.scrollX + (buttonRect.width / 2);

        // Set position
        tooltip.style.position = 'absolute';
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        tooltip.style.transform = 'translateX(-50%)';

        // Show the tooltip with animation
        tooltip.classList.add('visible');

        console.log('Showing Apple HIG tooltip with dimensions:',
            tooltipRect.width, 'x', tooltipRect.height);
    }, 10);
}

/**
 * Hides the Material Design 3 tooltip styled with Apple HIG
 */
function hideMD3Tooltip() {
    const tooltip = document.getElementById('startMigrationTooltip');
    if (tooltip) {
        // Apple HIG typically has a slight delay for dismissal
        // to prevent accidental dismissals
        setTimeout(() => {
            // Check if the mouse is over the tooltip
            const isMouseOverTooltip = false; // We're not allowing interaction with the tooltip

            if (!isMouseOverTooltip) {
                tooltip.classList.remove('visible');
                console.log('Hiding Apple HIG tooltip');
            }
        }, 100); // Slightly longer delay for Apple HIG
    }
}

/**
 * Updates the Apple HIG tooltip text based on the button's data-tooltip attribute
 */
function updateMD3TooltipText() {
    const startMigrationBtn = document.getElementById('startMigration');
    const tooltip = document.getElementById('startMigrationTooltip');

    if (startMigrationBtn && tooltip) {
        const tooltipText = startMigrationBtn.getAttribute('data-tooltip') || 'Connect accounts to start migration';

        // Only update if text has changed
        if (tooltip.textContent !== tooltipText) {
            tooltip.textContent = tooltipText;
            console.log('Updated Apple HIG tooltip text:', tooltipText);

            // If tooltip is currently visible, reposition it for the new text
            if (tooltip.classList.contains('visible')) {
                // Hide tooltip temporarily
                tooltip.classList.remove('visible');

                // Show tooltip again after a short delay to allow for repositioning
                setTimeout(() => {
                    showMD3Tooltip();
                }, 50);
            }
        }
    }
}

// Function to get Outlook OAuth URL
async function getOutlookOAuthUrl() {
    try {
        const response = await fetch('/outlook/auth-url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
        }

        const data = await response.json();
        return data.auth_url;
    } catch (error) {
        console.error('Error getting Outlook OAuth URL:', error);
        logToConsole(`Error getting Outlook OAuth URL: ${error.message}`, 'error');
        return null;
    }
}

// Function to connect to Outlook
async function connectToOutlook() {
    console.log('Global connectToOutlook function called');
    console.trace('Stacktrace for connectToOutlook call'); // Add stack trace to identify caller

    // Clear any existing token for testing
    localStorage.removeItem('outlookToken');
    localStorage.removeItem('outlookRefreshToken');

    // First check if user is already authenticated
    const outlookToken = localStorage.getItem('outlookToken');
    if (outlookToken) {
        console.log('User already has an Outlook token, not starting OAuth flow');
        return; // Prevent OAuth flow if already signed in
    }

    try {
        logToConsole('Initiating Outlook OAuth flow...', 'info');

        // Get the authorization URL
        const authUrl = await getOutlookOAuthUrl();
        console.log('Got Outlook auth URL:', authUrl);

        if (authUrl) {
            logToConsole('Redirecting to Outlook OAuth...', 'info');
            window.location.href = authUrl;
        } else {
            throw new Error('Failed to get Outlook OAuth URL');
        }
    } catch (error) {
        console.error('Error in connectToOutlook:', error);
        logToConsole(`Error connecting to Outlook: ${error.message}`, 'error');
    }
}

// Function to disconnect from Outlook
function disconnectOutlook() {
    console.log('Disconnecting Outlook account...');

    // Clear Outlook tokens from localStorage
    localStorage.removeItem('outlookToken');
    localStorage.removeItem('outlookUserInfo');

    // Update UI to show disconnected state
    const outlookConnectBtn = document.getElementById('outlookConnectBtn');
    const outlookConnectedInfo = document.getElementById('outlookConnectedInfo');

    if (outlookConnectBtn) outlookConnectBtn.style.display = 'block';
    if (outlookConnectedInfo) outlookConnectedInfo.style.display = 'none';

    // Update global state
    isDestinationConnected = false;

    // Update migration button state
    updateMigrationButtonState();

    // Add a log entry
    logToConsole('Outlook account disconnected. Please reconnect to continue.', 'warning');

    // Reload the page to ensure all UI elements are reset
    setTimeout(() => {
        window.location.reload();
    }, 2000);
}

// Function to update UI after Outlook connection
function updateUIAfterOutlookConnection(success, isDisconnecting = false) {
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');

    if (success) {
        // Get user email from localStorage or use a default
        let outlookUserEmail = localStorage.getItem('outlookUserEmail');
        console.log('Retrieved Outlook user email from localStorage:', outlookUserEmail);

        // Make sure we have a valid email or default value
        if (!outlookUserEmail || outlookUserEmail === 'undefined' || outlookUserEmail === 'null') {
            console.warn('Invalid or missing email, using default');
            outlookUserEmail = 'Microsoft Account';
            localStorage.setItem('outlookUserEmail', outlookUserEmail);
        }

        // Update button to show connected state with user email
        outlookAuthBtn.classList.add('connected');
        outlookAuthBtn.innerHTML = `
            <img src="/static/img/microsoft-logo.svg" alt="Microsoft Logo" class="auth-button-icon">
            <span style="flex: 1;">${outlookUserEmail}</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="#5f6368" class="logout-icon">
                <path d="M5 5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7v-2H5V5zm16 7l-4-4v3H9v2h8v3l4-4z"></path>
            </svg>
        `;

        // Add click event to disconnect
        outlookAuthBtn.removeEventListener('click', connectToOutlook);
        outlookAuthBtn.addEventListener('click', disconnectOutlook);

        // Hide Yahoo button when connected to Microsoft
        if (yahooAuthBtn) {
            yahooAuthBtn.style.display = 'none';
        }

        // Update state
        isDestinationConnected = true;

        // Enable start migration button if Gmail is also connected
        updateStartButtonState();
    } else {
        console.log('Outlook connection failed or disconnected, resetting UI state');

        // Only show error message if not intentionally disconnecting
        if (!isDisconnecting && outlookAuthBtn) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = 'Failed to connect to Outlook. Please try again.';
            outlookAuthBtn.parentNode.appendChild(errorMessage);
        }

        // Clear any stored tokens
        localStorage.removeItem('outlookToken');
        localStorage.removeItem('outlookRefreshToken');
        localStorage.removeItem('outlookUserEmail');

        // Reset the button
        if (outlookAuthBtn) {
            outlookAuthBtn.classList.remove('connected');
            outlookAuthBtn.innerHTML = `
                <img src="/static/img/microsoft-logo.svg" alt="Microsoft Logo" class="auth-button-icon">
                <span>Sign in with Microsoft</span>
            `;

            // Add click event to connect
            outlookAuthBtn.removeEventListener('click', disconnectOutlook);
            outlookAuthBtn.addEventListener('click', function(e) {
                e.preventDefault();
                localStorage.setItem('selectedDestinationProvider', 'outlook');
                connectToOutlook();
            });
        }

        // Show Yahoo button when disconnected from Microsoft
        if (yahooAuthBtn) {
            yahooAuthBtn.style.display = '';
        }

        // Update global state
        isDestinationConnected = false;

        // Force a page reload after a short delay to ensure UI is fully reset
        // Only reload if this was not an intentional disconnect (which already reloads)
        if (!isDisconnecting) {
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    }
}

// Function to update the start button state
function updateStartButtonState() {
    const startMigrationBtn = document.getElementById('startMigration');
    if (startMigrationBtn) {
        const isGmailConnected = localStorage.getItem('gmailToken') !== null;
        const isDestinationConnected =
            localStorage.getItem('outlookToken') !== null ||
            localStorage.getItem('yahooToken') !== null;

        // Update button state based on connection status
        startMigrationBtn.disabled = !(isGmailConnected && isDestinationConnected);

        // Update tooltip
        updateStartButtonTooltip();
    }
}

// Function to reset the migration button and UI
function resetMigrationButton() {
    console.log('Resetting migration button and UI');

    // Reset button state
    const startMigrationBtn = document.getElementById('startMigration');
    if (startMigrationBtn) {
        startMigrationBtn.disabled = false;
        startMigrationBtn.innerHTML = '<i class="fas fa-play"></i> Start Migration';
        startMigrationBtn.classList.remove('button-pressed');
    }

    // Close the event source if it exists
    if (window.migrationEventSource) {
        console.log('Closing migration event source');
        window.migrationEventSource.close();
        window.migrationEventSource = null;
    }

    // Hide the migration status section after a delay
    setTimeout(() => {
        const migrationStatus = document.getElementById('migrationStatus');
        if (migrationStatus) {
            migrationStatus.style.display = 'none';
        }
    }, 3000); // Keep visible for 3 seconds so user can see final state

    // Reset progress indicators
    const progressBar = document.getElementById('progressBar');
    const progressPercentage = document.getElementById('progressPercentage');
    const migrationProgress = document.getElementById('migrationProgress');

    if (progressBar) progressBar.style.width = '0%';
    if (progressPercentage) progressPercentage.textContent = '0%';
    if (migrationProgress) migrationProgress.textContent = '0/0 emails processed';

    // Reset counters
    const completedCount = document.getElementById('completedCount');
    const pendingCount = document.getElementById('pendingCount');
    const failedCount = document.getElementById('failedCount');

    if (completedCount) completedCount.textContent = '0';
    if (pendingCount) pendingCount.textContent = '0';
    if (failedCount) failedCount.textContent = '0';

    console.log('Migration UI reset complete');
}

// Function to initialize OAuth settings modal
function initializeOAuthSettingsModal() {
    console.log('Initializing OAuth settings modal...');

    const oauthSettingsBtn = document.getElementById('oauthSettingsBtn');
    const oauthSettingsModal = document.getElementById('oauthSettingsModal');
    const closeModal = document.querySelector('.close-modal');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    if (!oauthSettingsBtn || !oauthSettingsModal) {
        console.error('OAuth settings modal elements not found');
        return;
    }

    // Open modal when settings button is clicked
    oauthSettingsBtn.addEventListener('click', function() {
        oauthSettingsModal.style.display = 'block';
    });

    // Close modal when close button is clicked
    if (closeModal) {
        closeModal.addEventListener('click', function() {
            oauthSettingsModal.style.display = 'none';
        });
    }

    // Close modal when clicking outside of it
    window.addEventListener('click', function(event) {
        if (event.target === oauthSettingsModal) {
            oauthSettingsModal.style.display = 'none';
        }
    });

    // Tab functionality
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tab = this.getAttribute('data-tab');

            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to current button and content
            this.classList.add('active');
            document.getElementById(`${tab}-tab`).classList.add('active');
        });
    });

    // Initialize form values from localStorage if available
    const gmailClientId = localStorage.getItem('gmailClientId');
    const gmailClientSecret = localStorage.getItem('gmailClientSecret');
    const gmailRedirectUri = localStorage.getItem('gmailRedirectUri');

    const outlookClientId = localStorage.getItem('outlookClientId');
    const outlookClientSecret = localStorage.getItem('outlookClientSecret');
    const outlookRedirectUri = localStorage.getItem('outlookRedirectUri');

    const yahooClientId = localStorage.getItem('yahooClientId');
    const yahooClientSecret = localStorage.getItem('yahooClientSecret');
    const yahooRedirectUri = localStorage.getItem('yahooRedirectUri');

    // Set form values if available
    if (gmailClientId) document.getElementById('gmailClientId').value = gmailClientId;
    if (gmailClientSecret) document.getElementById('gmailClientSecret').value = gmailClientSecret;
    if (gmailRedirectUri) document.getElementById('gmailRedirectUri').value = gmailRedirectUri;

    if (outlookClientId) document.getElementById('outlookClientId').value = outlookClientId;
    if (outlookClientSecret) document.getElementById('outlookClientSecret').value = outlookClientSecret;
    if (outlookRedirectUri) document.getElementById('outlookRedirectUri').value = outlookRedirectUri;

    if (yahooClientId) document.getElementById('yahooClientId').value = yahooClientId;
    if (yahooClientSecret) document.getElementById('yahooClientSecret').value = yahooClientSecret;
    if (yahooRedirectUri) document.getElementById('yahooRedirectUri').value = yahooRedirectUri;

    // Handle form submissions
    const gmailOAuthForm = document.getElementById('gmailOAuthForm');
    const outlookOAuthForm = document.getElementById('outlookOAuthForm');
    const yahooOAuthForm = document.getElementById('yahooOAuthForm');

    if (gmailOAuthForm) {
        gmailOAuthForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const clientId = document.getElementById('gmailClientId').value;
            const clientSecret = document.getElementById('gmailClientSecret').value;
            const redirectUri = document.getElementById('gmailRedirectUri').value;

            localStorage.setItem('gmailClientId', clientId);
            localStorage.setItem('gmailClientSecret', clientSecret);
            localStorage.setItem('gmailRedirectUri', redirectUri);

            alert('Gmail OAuth settings saved!');
        });
    }

    if (outlookOAuthForm) {
        outlookOAuthForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const clientId = document.getElementById('outlookClientId').value;
            const clientSecret = document.getElementById('outlookClientSecret').value;
            const redirectUri = document.getElementById('outlookRedirectUri').value;

            localStorage.setItem('outlookClientId', clientId);
            localStorage.setItem('outlookClientSecret', clientSecret);
            localStorage.setItem('outlookRedirectUri', redirectUri);

            alert('Outlook OAuth settings saved!');
        });
    }

    if (yahooOAuthForm) {
        yahooOAuthForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const clientId = document.getElementById('yahooClientId').value;
            const clientSecret = document.getElementById('yahooClientSecret').value;
            const redirectUri = document.getElementById('yahooRedirectUri').value;

            localStorage.setItem('yahooClientId', clientId);
            localStorage.setItem('yahooClientSecret', clientSecret);
            localStorage.setItem('yahooRedirectUri', redirectUri);

            alert('Yahoo OAuth settings saved!');
        });
    }
}

// Function to connect to Yahoo
function connectToYahoo() {
    console.log('Connecting to Yahoo');
    logToConsole('Connecting to Yahoo...', 'info');

    // Simulate successful connection for now
    // In a real implementation, this would involve OAuth flow
    setTimeout(() => {
        // Store a dummy token
        localStorage.setItem('yahooToken', 'dummy-yahoo-token');
        localStorage.setItem('yahooUserEmail', 'user@yahoo.com');

        // Update UI
        updateUIAfterYahooConnection(true);

        logToConsole('Connected to Yahoo', 'success');
    }, 1500);
}

// Function to update UI after Yahoo connection
function updateUIAfterYahooConnection(success, isDisconnecting = false) {
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');

    if (success) {
        // Update button to show connected state
        yahooAuthBtn.classList.add('connected');
        yahooAuthBtn.innerHTML = `
            <img src="/static/img/yahoo-white-icon.svg" alt="Yahoo Logo" class="auth-button-icon">
            <span style="flex: 1;">Yahoo Account</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="#5f6368" class="logout-icon">
                <path d="M5 5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7v-2H5V5zm16 7l-4-4v3H9v2h8v3l4-4z"></path>
            </svg>
        `;

        // Add click event to disconnect
        yahooAuthBtn.removeEventListener('click', connectToYahoo);
        yahooAuthBtn.addEventListener('click', disconnectYahoo);

        // Hide Microsoft button when connected to Yahoo
        if (outlookAuthBtn) {
            outlookAuthBtn.style.display = 'none';
        }

        // Update state
        isDestinationConnected = true;

        // Enable start migration button if Gmail is also connected
        updateStartButtonState();
    } else {
        // Only show error message if not intentionally disconnecting
        if (!isDisconnecting && yahooAuthBtn) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = 'Failed to connect to Yahoo. Please try again.';
            yahooAuthBtn.parentNode.appendChild(errorMessage);

            // Remove the error message after 5 seconds
            setTimeout(() => {
                if (errorMessage.parentNode === yahooAuthBtn.parentNode) {
                    yahooAuthBtn.parentNode.removeChild(errorMessage);
                }
            }, 5000);
        }

        // Clear any stored tokens
        localStorage.removeItem('yahooToken');
        localStorage.removeItem('yahooRefreshToken');
        localStorage.removeItem('yahooUserEmail');

        // Reset the button
        if (yahooAuthBtn) {
            yahooAuthBtn.classList.remove('connected');
            yahooAuthBtn.innerHTML = `
                <img src="/static/img/yahoo-white-icon.svg" alt="Yahoo Logo" class="auth-button-icon">
                <span>Sign in with Yahoo</span>
            `;

            // Add click event to connect
            yahooAuthBtn.removeEventListener('click', disconnectYahoo);
            yahooAuthBtn.addEventListener('click', function(e) {
                e.preventDefault();
                localStorage.setItem('selectedDestinationProvider', 'yahoo');
                connectToYahoo();
            });
        }

        // Show Microsoft button when disconnected from Yahoo
        if (outlookAuthBtn) {
            outlookAuthBtn.style.display = '';
        }
    }
}

// Function to disconnect from Yahoo
function disconnectYahoo() {
    console.log('Disconnecting from Yahoo');
    logToConsole('Disconnecting from Yahoo...', 'info');

    // Clear tokens from localStorage
    localStorage.removeItem('yahooToken');
    localStorage.removeItem('yahooRefreshToken');
    localStorage.removeItem('yahooUserEmail');

    // Update UI with isDisconnecting=true to prevent showing error message
    updateUIAfterYahooConnection(false, true);

    // Update start button state
    updateStartButtonState();

    logToConsole('Disconnected from Yahoo', 'success');
}

// Function to handle the download report button
function handleDownloadReport() {
    const migrationLog = document.getElementById('migrationLog');
    if (!migrationLog) return;

    // Get all log entries
    const logEntries = migrationLog.querySelectorAll('.log-entry');
    if (logEntries.length === 0) return;

    // Create report content
    let reportContent = "Gmail Migration Report\n";
    reportContent += "======================\n\n";
    reportContent += `Generated: ${new Date().toLocaleString()}\n\n`;

    // Add log entries
    reportContent += "Migration Log:\n";
    reportContent += "--------------\n";
    logEntries.forEach(entry => {
        const timestamp = entry.querySelector('.timestamp').textContent;
        const message = entry.querySelector('.message').textContent;
        const type = entry.classList.contains('error') ? 'ERROR' :
                     entry.classList.contains('warning') ? 'WARNING' :
                     entry.classList.contains('success') ? 'SUCCESS' : 'INFO';

        reportContent += `[${timestamp}] [${type}] ${message}\n`;
    });

    // Get statistics
    const successCount = document.getElementById('successCount')?.textContent || '0';
    const failedCount = document.getElementById('failedCount')?.textContent || '0';
    const pendingCount = document.getElementById('pendingCount')?.textContent || '0';

    // Add statistics to report
    reportContent += "\nMigration Statistics:\n";
    reportContent += "--------------------\n";
    reportContent += `Completed: ${successCount}\n`;
    reportContent += `Failed: ${failedCount}\n`;
    reportContent += `Pending: ${pendingCount}\n`;

    // Create blob and download
    const blob = new Blob([reportContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gmail-migration-report-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Initialize the application when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded, initializing application...');
    initializeApp();

    // Ensure tooltip is created after a short delay to allow other elements to initialize
    setTimeout(function() {
        createMD3Tooltip();
        console.log('Tooltip initialization completed');
    }, 500);

    // Add window resize event listener to reposition tooltip if visible
    window.addEventListener('resize', function() {
        const tooltip = document.getElementById('startMigrationTooltip');
        const startMigrationBtn = document.getElementById('startMigration');

        if (tooltip && startMigrationBtn && tooltip.classList.contains('visible')) {
            // Reposition tooltip
            const buttonRect = startMigrationBtn.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();

            const top = buttonRect.top + window.scrollY - tooltipRect.height - 12;
            const left = buttonRect.left + window.scrollX + (buttonRect.width / 2);

            tooltip.style.top = `${top}px`;
            tooltip.style.left = `${left}px`;

            console.log('Repositioned tooltip after window resize');
        }
    });
});

// Define the implementation of the migration function
window.performMigrationImpl = function() {
    console.log('%c MIGRATION STARTED FROM MAIN.JS! ', 'background: #4CAF50; color: white; font-size: 16px; padding: 5px;');

    // Get the selected destination
    const destinationSelect = document.getElementById('destinationSelect');
    const destination = destinationSelect ? destinationSelect.value : 'outlook';

    // Get the appropriate tokens
    const gmailToken = localStorage.getItem('gmailToken');
    const outlookToken = localStorage.getItem('outlookToken');
    const yahooToken = localStorage.getItem('yahooToken');
    const gmailRefreshToken = localStorage.getItem('gmailRefreshToken');
    const gmailClientId = localStorage.getItem('gmailClientId');
    const gmailClientSecret = localStorage.getItem('gmailClientSecret');

    // Debug token information
    console.log('Gmail token available:', !!gmailToken);
    console.log('Gmail refresh token available:', !!gmailRefreshToken);
    console.log('Gmail client ID available:', !!gmailClientId);
    console.log('Gmail client secret available:', !!gmailClientSecret);
    console.log('Outlook token available:', !!outlookToken);

    // Add log entry to the migration log
    function addLogEntry(message, type = 'info') {
        const migrationLog = document.getElementById('migrationLog');
        if (!migrationLog) return;

        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;

        const timestamp = document.createElement('span');
        timestamp.className = 'timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();

        const messageSpan = document.createElement('span');
        messageSpan.className = 'message';
        messageSpan.textContent = message;

        logEntry.appendChild(timestamp);
        logEntry.appendChild(messageSpan);
        migrationLog.appendChild(logEntry);

        // Scroll to bottom
        migrationLog.scrollTop = migrationLog.scrollHeight;

        // Also log to console
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    // Show the migration status section
    const migrationStatus = document.getElementById('migrationStatus');
    if (migrationStatus) {
        migrationStatus.style.display = 'block';
        addLogEntry('Starting migration process...', 'info');
    }

    // Update progress indicators
    function updateProgress(processed, total) {
        const progressBarFill = document.getElementById('progressBarFill');
        const processedCount = document.getElementById('processedCount');
        const progressPercentage = document.getElementById('progressPercentage');
        const successCount = document.getElementById('successCount');
        const pendingCount = document.getElementById('pendingCount');

        if (progressBarFill && processedCount && progressPercentage) {
            const percent = total > 0 ? Math.round((processed / total) * 100) : 0;
            progressBarFill.style.width = `${percent}%`;
            processedCount.textContent = `${processed}/${total} emails processed`;
            progressPercentage.textContent = `${percent}%`;

            if (successCount) successCount.textContent = processed;
            if (pendingCount) pendingCount.textContent = total - processed;
        }
    }

    // Test Outlook token if available
    if (outlookToken) {
        addLogEntry('Testing Outlook token...', 'info');
        fetch('https://graph.microsoft.com/v1.0/me', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${outlookToken}`
            }
        })
        .then(response => {
            if (response.ok) {
                addLogEntry('Outlook token is valid', 'success');
                return response.json();
            } else {
                addLogEntry(`Outlook token validation failed: ${response.status}`, 'error');
                throw new Error(`Outlook token validation failed: ${response.status}`);
            }
        })
        .then(data => {
            addLogEntry(`Connected as ${data.displayName || data.userPrincipalName}`, 'info');
        })
        .catch(error => {
            console.error('Error testing Outlook token:', error);
            addLogEntry(`Error testing Outlook token: ${error.message}`, 'error');

            // If token is invalid, clear it and show reconnect message
            if (error.message.includes('401')) {
                localStorage.removeItem('outlookToken');
                localStorage.removeItem('outlookRefreshToken');

                const startMigrationBtn = document.getElementById('startMigration');
                if (startMigrationBtn) {
                    startMigrationBtn.disabled = false;
                    startMigrationBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Please reconnect to Outlook';
                    startMigrationBtn.classList.remove('button-pressed');
                    startMigrationBtn.classList.add('error');

                    // Update tooltip to show reconnection needed
                    startMigrationBtn.setAttribute('data-tooltip', 'Your Outlook session has expired. Please reconnect your Microsoft account.');

                    // Reset after 3 seconds
                    setTimeout(() => {
                        startMigrationBtn.innerHTML = '<i class="fas fa-play"></i> Start Migration';
                        startMigrationBtn.classList.remove('error');

                        // Reset tooltip
                        startMigrationBtn.setAttribute('data-tooltip', 'Please connect both source and destination accounts to start migration');
                    }, 3000);
                }
                return;
            }
        });
    }

    // Get additional Gmail info if available
    const gmailUserInfo = localStorage.getItem('gmailUserInfo');

    // Check if we're properly authenticated
    if (!gmailToken || (!outlookToken && !yahooToken)) {
        console.error('Authentication required: Please connect both Gmail and destination accounts');
        addLogEntry('Authentication required: Please connect both Gmail and destination accounts', 'error');

        // Reset button state with error
        const startMigrationBtn = document.getElementById('startMigration');
        if (startMigrationBtn) {
            startMigrationBtn.disabled = false;
            startMigrationBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Authentication Required';
            startMigrationBtn.classList.remove('button-pressed');
            startMigrationBtn.classList.add('error');

            // Update tooltip to show authentication needed
            startMigrationBtn.setAttribute('data-tooltip', 'Please connect both Gmail and destination accounts before starting migration');

            // Reset after 3 seconds
            setTimeout(() => {
                startMigrationBtn.innerHTML = '<i class="fas fa-play"></i> Start Migration';
                startMigrationBtn.classList.remove('error');

                // Reset tooltip
                startMigrationBtn.setAttribute('data-tooltip', 'Please connect both source and destination accounts to start migration');
            }, 3000);
        }
        return;
    }

    // Determine which token to use based on destination
    let destinationToken = outlookToken;
    if (destination === 'yahoo') {
        destinationToken = yahooToken;
    }

    // Create a complete credentials object
    const credentials = {
        gmail: {
            token: gmailToken,
            user_info: gmailUserInfo ? JSON.parse(gmailUserInfo) : null,
            client_id: gmailClientId || '',
            client_secret: gmailClientSecret || '',
            refresh_token: gmailRefreshToken || '',
            token_uri: 'https://oauth2.googleapis.com/token'
        },
        destination: {
            token: destinationToken,
            provider: destination
        }
    };

    // Debug the credentials object (without exposing sensitive data)
    console.log('Credentials prepared:', {
        gmail: {
            token: gmailToken ? 'present' : 'missing',
            refresh_token: gmailRefreshToken ? 'present' : 'missing',
            client_id: gmailClientId ? 'present' : 'missing',
            client_secret: gmailClientSecret ? 'present' : 'missing',
            user_info: gmailUserInfo ? 'present' : 'missing'
        },
        destination: {
            token: destinationToken ? 'present' : 'missing',
            provider: destination
        }
    });

    if (destination === 'outlook') {
        console.log('Starting migration from Gmail to Outlook...');
        addLogEntry('Starting migration from Gmail to Outlook...', 'info');

        // First migrate labels
        addLogEntry('Step 1/2: Migrating Gmail labels to Outlook folders...', 'info');
        fetch('/migration/gmail-to-outlook/labels', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${gmailToken}`,
                'X-Destination-Token': `${destinationToken}`
            },
            body: JSON.stringify(credentials)
        })
        .then(response => {
            if (!response.ok) {
                if (response.status === 401) {
                    addLogEntry('Authentication failed. Please reconnect your accounts.', 'error');
                    throw new Error('Authentication failed. Please reconnect your accounts.');
                } else if (response.status === 500) {
                    // Try to get more details from the error response
                    return response.text().then(text => {
                        try {
                            const errorData = JSON.parse(text);
                            addLogEntry(`Server error: ${errorData.detail || 'Unknown error'}`, 'error');
                            console.error('Server error details:', errorData);
                            throw new Error('Server error. Please check that both accounts are properly connected.');
                        } catch (e) {
                            addLogEntry(`Server error: ${text}`, 'error');
                            console.error('Server error details:', text);
                            throw new Error('Server error. Please check that both accounts are properly connected.');
                        }
                    });
                } else {
                    addLogEntry(`Label migration failed with status: ${response.status}`, 'error');
                    throw new Error(`Label migration failed with status: ${response.status}`);
                }
            }
            return response.json();
        })
        .then(data => {
            console.log('Labels migrated successfully:', data);
            const labelCount = Object.keys(data).length;
            addLogEntry(`Successfully migrated ${labelCount} labels to Outlook folders`, 'success');

            // Now migrate all emails
            addLogEntry('Step 2/2: Migrating emails...', 'info');
            return fetch('/migration/gmail-to-outlook/all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${gmailToken}`,
                    'X-Destination-Token': `${destinationToken}`
                },
                body: JSON.stringify({
                    max_emails_per_label: 100,
                    credentials: credentials
                })
            });
        })
        .then(response => {
            console.log('Migration response status:', response.status);
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`Email migration failed with status: ${response.status}${text ? ` - ${text}` : ''}`);
                });
            }
            return response.json();
        })
        .then(migrationResult => {
            console.log('Migration result:', migrationResult);

            // Log the results
            const successCount = migrationResult.successful || 0;
            const totalCount = migrationResult.total || 0;
            const failedCount = migrationResult.failed || 0;

            logToConsole(`Migration complete: ${successCount} of ${totalCount} emails migrated successfully`, 'success');

            if (failedCount > 0) {
                logToConsole(`[WARNING] ${failedCount} emails failed to migrate`, 'warning');
            }

            // The UI will be updated by the SSE connection
        })
        .catch(error => {
            console.error('Migration error:', error);
            logToConsole(`Migration failed: ${error.message}`, 'error');

            // Update button state
            const startMigrationBtn = document.getElementById('startMigration');
            if (startMigrationBtn) {
                startMigrationBtn.disabled = false;
                startMigrationBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Migration Failed';
                startMigrationBtn.classList.remove('button-pressed');
            }

            // Close the event source
            if (migrationEventSource) {
                migrationEventSource.close();
                migrationEventSource = null;
            }
        });
    } else {
        console.warn(`Migration to ${destination} not implemented yet`);
        addLogEntry(`Migration to ${destination} not implemented yet`, 'warning');

        // Reset button state
        const startMigrationBtn = document.getElementById('startMigration');
        if (startMigrationBtn) {
            startMigrationBtn.disabled = false;
            startMigrationBtn.innerHTML = '<i class="fas fa-play"></i> Start Migration';
            startMigrationBtn.classList.remove('button-pressed');
        }
    }
};

// Function to update the migration button state based on connection status
function updateMigrationButtonState() {
    const startMigrationBtn = document.getElementById('startMigration');
    if (!startMigrationBtn) return;

    // Enable the button only if both Gmail and destination are connected
    const isEnabled = isGmailConnected && isDestinationConnected;
    startMigrationBtn.disabled = !isEnabled;

    // Update tooltip
    if (isEnabled) {
        startMigrationBtn.removeAttribute('data-tooltip');
    } else {
        startMigrationBtn.setAttribute('data-tooltip', 'Please connect both source and destination accounts to start migration');
    }

    console.log(`Migration button state updated: ${isEnabled ? 'enabled' : 'disabled'}`);
}

// Helper function to determine log type
function getLogType(message) {
    if (!message) return 'info';

    if (message.includes('ERROR') || message.includes('failed') || message.includes('Failed')) {
        return 'error';
    } else if (message.includes('WARNING') || message.includes('warning')) {
        return 'warning';
    } else if (message.includes('SUCCESS') || message.includes('success') || message.includes('Successfully')) {
        return 'success';
    }
    return 'info';
}

// Helper function to add a log entry
function addLogEntry(message, type = 'info') {
    const migrationLog = document.getElementById('migrationLog');
    if (!migrationLog) return;

    const logEntry = document.createElement('div');
    logEntry.className = type;

    const timestamp = document.createElement('span');
    timestamp.className = 'timestamp';
    timestamp.textContent = new Date().toLocaleTimeString() + ' ';

    const messageSpan = document.createElement('span');
    messageSpan.className = 'message';
    messageSpan.textContent = message;

    logEntry.appendChild(timestamp);
    logEntry.appendChild(messageSpan);
    migrationLog.appendChild(logEntry);

    // Scroll to bottom
    migrationLog.scrollTop = migrationLog.scrollHeight;
}

// Function to force reset all authentication state and UI
function forceResetAuthState() {
    console.log('Force resetting all authentication state and UI');

    // Clear all authentication tokens from localStorage
    localStorage.removeItem('gmailToken');
    localStorage.removeItem('gmailRefreshToken');
    localStorage.removeItem('gmailUserInfo');
    localStorage.removeItem('outlookToken');
    localStorage.removeItem('outlookRefreshToken');
    localStorage.removeItem('outlookUserEmail');
    localStorage.removeItem('yahooToken');
    localStorage.removeItem('yahooUserEmail');

    // Reset global state variables
    isGmailConnected = false;
    isDestinationConnected = false;

    // Reset Gmail UI
    const gmailAuthContainer = document.getElementById('googleSignInButtonContainer');
    if (gmailAuthContainer) {
        gmailAuthContainer.innerHTML = '';

        // Create a new Google Sign-In button
        const button = document.createElement('button');
        button.className = 'google-auth-button';
        button.innerHTML = `
            <img src="/static/img/google-logo.svg" alt="Google Logo" class="auth-button-icon">
            <span>Sign in with Google</span>
        `;

        // Add click event to initiate Google sign-in
        button.addEventListener('click', async function() {
            const url = await getGmailOAuthUrl();
            if (url) {
                window.location.href = url;
            }
        });

        // Add the button to the container
        gmailAuthContainer.appendChild(button);
    }

    // Reset Outlook UI
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    if (outlookAuthBtn) {
        outlookAuthBtn.classList.remove('connected');
        outlookAuthBtn.innerHTML = `
            <img src="/static/img/microsoft-logo.svg" alt="Microsoft Logo" class="auth-button-icon">
            <span>Sign in with Microsoft</span>
        `;

        // Remove any existing event listeners
        const newOutlookBtn = outlookAuthBtn.cloneNode(true);
        outlookAuthBtn.parentNode.replaceChild(newOutlookBtn, outlookAuthBtn);

        // Add click event to connect
        newOutlookBtn.addEventListener('click', function(e) {
            e.preventDefault();
            localStorage.setItem('selectedDestinationProvider', 'outlook');
            connectToOutlook();
        });
    }

    // Reset Yahoo UI
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');
    if (yahooAuthBtn) {
        yahooAuthBtn.style.display = '';
        yahooAuthBtn.classList.remove('connected');
        yahooAuthBtn.innerHTML = `
            <img src="/static/img/yahoo-white-icon.svg" alt="Yahoo Logo" class="auth-button-icon">
            <span>Sign in with Yahoo</span>
        `;

        // Remove any existing event listeners
        const newYahooBtn = yahooAuthBtn.cloneNode(true);
        yahooAuthBtn.parentNode.replaceChild(newYahooBtn, yahooAuthBtn);

        // Add click event to connect
        newYahooBtn.addEventListener('click', function(e) {
            e.preventDefault();
            localStorage.setItem('selectedDestinationProvider', 'yahoo');
            connectToYahoo();
        });
    }

    // Disable the start migration button
    updateStartButtonState();

    console.log('Authentication state and UI reset complete');
}
