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
    // Toggle visibility of destination options container
    const destinationOptionsContainer = document.getElementById('destination-options-container');
    if (destinationOptionsContainer) {
        destinationOptionsContainer.classList.toggle('hidden');
        logToConsole('Showing destination options...', 'info');
    } else {
        console.error('Destination options container not found');
        logToConsole('Error: Could not find destination options container', 'error');
    }
}

// Function to initialize the application
function initializeApp() {
    console.log('Initializing application...');

    // Check if Gmail token exists in localStorage
    const gmailToken = localStorage.getItem('gmailToken');
    if (gmailToken) {
        // User is already authenticated, update UI
        updateUIAfterGmailConnection(true);
    } else {
        // User is not authenticated, show connect button
        updateUIAfterGmailConnection(false);
    }

    // Disable destination buttons by default
    const destinationButtons = document.querySelectorAll('.destination-option');
    destinationButtons.forEach(button => {
        button.disabled = true;
    });

    // Initialize destination selection
    initializeDestinationSelection();

    // Initialize advanced options toggle
    initializeAdvancedOptionsToggle();

    // Initialize batch size slider
    initializeBatchSizeSlider();

    // Initialize migration options
    initializeMigrationOptions();

    // Check for OAuth callback
    handleOAuthCallback();

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

    // If we have code or state, we might be in a callback
    if (code || state) {
        console.log('Found OAuth parameters in URL');
        logToConsole('Processing OAuth callback...', 'info');

        // Handle processing if needed - usually this is handled by the backend

        // Clean up URL - remove parameters to prevent reprocessing on refresh
        if (history.pushState) {
            const newurl = window.location.protocol + '//' + window.location.host + window.location.pathname;
            window.history.pushState({path: newurl}, '', newurl);
            console.log('Cleaned up URL parameters');
        }
    } else {
        console.log('No OAuth callback parameters found in URL');
    }
}

// Function to handle destination provider selection
function initializeDestinationSelection() {
    console.log('Initializing destination selection');
    const outlookAuthBtn = document.getElementById('outlookAuthBtn');
    const yahooAuthBtn = document.getElementById('yahooAuthBtn');
    const outlookAuthSection = document.getElementById('outlookAuthSection');
    const yahooAuthSection = document.getElementById('yahooAuthSection');

    console.log('Outlook auth button found:', !!outlookAuthBtn);
    console.log('Yahoo auth button found:', !!yahooAuthBtn);
    console.log('Outlook auth section found:', !!outlookAuthSection);
    console.log('Yahoo auth section found:', !!yahooAuthSection);

    if (!outlookAuthBtn || !yahooAuthBtn) {
        console.error('Destination auth buttons not found');
        return;
    }

    // Add click event listeners to auth buttons
    outlookAuthBtn.addEventListener('click', function(e) {
        // Prevent default to handle the auth flow ourselves
        e.preventDefault();

        const provider = this.getAttribute('data-provider');
        console.log('Outlook auth button clicked, provider:', provider);

        // Store selected provider
        localStorage.setItem('selectedDestinationProvider', 'outlook');
        console.log('Provider saved to localStorage: outlook');

        // Call the connect function directly
        connectToOutlook();
    });

    yahooAuthBtn.addEventListener('click', function(e) {
        // Prevent default to handle the auth flow ourselves
        e.preventDefault();

        const provider = this.getAttribute('data-provider');
        console.log('Yahoo auth button clicked, provider:', provider);

        // Store selected provider
        localStorage.setItem('selectedDestinationProvider', 'yahoo');
        console.log('Provider saved to localStorage: yahoo');

        // Call the connect function directly
        connectToYahoo();
    });

    // Initialize the global connect functions
    window.connectToOutlook = function() {
        console.log('Global connectToOutlook function called');
        // This would be implemented with actual OAuth flow
        // For now, we'll simulate a successful connection

        setTimeout(() => {
            // Update button to show connected state
            outlookAuthBtn.classList.add('connected');
            outlookAuthBtn.innerHTML = `
                <img src="/static/img/microsoft-logo.svg" alt="Microsoft Logo" class="auth-button-icon">
                <span>Connected to Microsoft</span>
            `;

            // Enable start migration button
            const startMigrationBtn = document.getElementById('startMigration');
            if (startMigrationBtn) {
                startMigrationBtn.disabled = false;
            }
        }, 1500);
    };

    window.connectToYahoo = function() {
        console.log('Global connectToYahoo function called');
        // This would be implemented with actual OAuth flow
        // For now, we'll simulate a successful connection

        setTimeout(() => {
            // Update button to show connected state
            yahooAuthBtn.classList.add('connected');
            yahooAuthBtn.innerHTML = `
                <img src="/static/img/yahoo-white-icon.svg" alt="Yahoo Logo" class="auth-button-icon">
                <span>Connected to Yahoo</span>
            `;

            // Enable start migration button
            const startMigrationBtn = document.getElementById('startMigration');
            if (startMigrationBtn) {
                startMigrationBtn.disabled = false;
            }
        }, 1500);
    };
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
