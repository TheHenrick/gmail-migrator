/**
 * Gmail Migrator - Main JavaScript
 */

console.log('main.js loaded');

// Global state variables
let isGmailConnected = false;
let isDestinationConnected = false;

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

// Add log entry to both console and UI
function logToConsole(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = { timestamp, message, type };

    // Initialize migration.logs if it doesn't exist
    if (typeof migration === 'undefined' || !migration.logs) {
        window.migration = window.migration || {};
        migration.logs = migration.logs || [];
    }

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

            if (data.refresh_token) {
                localStorage.setItem('gmailRefreshToken', data.refresh_token);
                logToConsole('Refresh token stored', 'info');
            }

            return true;
        } else {
            logToConsole('No access token in response', 'error');
            return false;
        }
    } catch (error) {
        logToConsole('Error exchanging credential: ' + error, 'error');
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
        // Show error message
        const gmailAuthContainer = document.getElementById('googleSignInButtonContainer');
        if (gmailAuthContainer) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = 'Failed to connect to Gmail. Please try again.';
            gmailAuthContainer.appendChild(errorMessage);

            // Remove the error message after 5 seconds
            setTimeout(() => {
                if (errorMessage.parentNode === gmailAuthContainer) {
                    gmailAuthContainer.removeChild(errorMessage);
                }
            }, 5000);
        }

        // Clear any stored tokens
        localStorage.removeItem('gmailToken');
        localStorage.removeItem('gmailRefreshToken');
        localStorage.removeItem('gmailUserInfo');

        // Update the Gmail auth button
        updateGmailAuthButton();
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
    logToConsole('Disconnecting from Gmail', 'info');

    // Clear tokens and user info
    localStorage.removeItem('gmailToken');
    localStorage.removeItem('gmailRefreshToken');
    localStorage.removeItem('gmailUserInfo');

    // Update the UI
    updateGmailAuthButton();

    // Disable destination buttons
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');

    if (outlookAuthBtn) outlookAuthBtn.disabled = true;
    if (yahooAuthBtn) yahooAuthBtn.disabled = true;

    // Update state
    isGmailConnected = false;
    updateStartButtonTooltip();

    // Disable the start migration button
    const startMigrationBtn = document.getElementById('startMigration');
    if (startMigrationBtn) {
        startMigrationBtn.disabled = true;
    }
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

    // Check for OAuth callback parameters
    handleOAuthCallback();

    // Initialize Google Sign-In
    initializeGoogleSignIn();

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

    // Animate UI elements
    animateUIElements();
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
    console.log('Disconnecting from Outlook');
    logToConsole('Disconnecting from Outlook...', 'info');

    // Clear tokens from localStorage
    localStorage.removeItem('outlookToken');
    localStorage.removeItem('outlookRefreshToken');
    localStorage.removeItem('outlookUserEmail');

    // Update UI with isDisconnecting=true to prevent showing error message
    updateUIAfterOutlookConnection(false, true);

    // Update start button state
    updateStartButtonState();

    logToConsole('Disconnected from Outlook', 'success');
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
        // Only show error message if not intentionally disconnecting
        if (!isDisconnecting && outlookAuthBtn) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = 'Failed to connect to Outlook. Please try again.';
            outlookAuthBtn.parentNode.appendChild(errorMessage);

            // Remove the error message after 5 seconds
            setTimeout(() => {
                if (errorMessage.parentNode === outlookAuthBtn.parentNode) {
                    outlookAuthBtn.parentNode.removeChild(errorMessage);
                }
            }, 5000);
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

        startMigrationBtn.disabled = !(isGmailConnected && isDestinationConnected);

        // Update tooltip
        updateStartButtonTooltip();
    }
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
