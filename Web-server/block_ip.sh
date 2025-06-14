#!/bin/bash

# Professional IP Blocking Script
# Description: Securely blocks malicious IP addresses using iptables
# Author: Security Team
# Version: 2.0

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_FILE="/var/log/security/ip_blocking.log"
readonly CHAIN_NAME="SECURITY_BLOCK"
readonly MAX_BLOCKED_IPS=10000

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    
    # Log to file and stdout
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE" 2>/dev/null || true
    
    # Also log to syslog
    logger -t "$SCRIPT_NAME" "[$level] $message" 2>/dev/null || true
}

# Error handling
error_exit() {
    log "ERROR" "$1"
    echo -e "${RED}❌ Error: $1${NC}" >&2
    exit 1
}

# Warning function
warn() {
    log "WARN" "$1"
    echo -e "${YELLOW}⚠️  Warning: $1${NC}" >&2
}

# Success function
success() {
    log "INFO" "$1"
    echo -e "${GREEN}✅ $1${NC}"
}

# Info function
info() {
    log "INFO" "$1"
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root (use sudo)"
    fi
}

# Validate IP address format
validate_ip() {
    local ip="$1"
    
    # Check if IP is empty
    if [[ -z "$ip" ]]; then
        return 1
    fi
    
    # Check IP format using regex
    if [[ $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        # Check each octet is <= 255
        IFS='.' read -ra ADDR <<< "$ip"
        for octet in "${ADDR[@]}"; do
            if [[ $octet -gt 255 ]]; then
                return 1
            fi
        done
        return 0
    fi
    
    return 1
}

# Check if IP is private/reserved
is_private_ip() {
    local ip="$1"
    
    # Private IP ranges
    local private_ranges=(
        "10.0.0.0/8"
        "172.16.0.0/12"
        "192.168.0.0/16"
        "127.0.0.0/8"
        "169.254.0.0/16"
        "224.0.0.0/4"
        "240.0.0.0/4"
    )
    
    for range in "${private_ranges[@]}"; do
        if ipcalc -c "$range" "$ip" 2>/dev/null; then
            return 0
        fi
    done
    
    return 1
}

# Initialize security chain
init_security_chain() {
    # Create custom chain if it doesn't exist
    if ! iptables -L "$CHAIN_NAME" -n >/dev/null 2>&1; then
        iptables -N "$CHAIN_NAME"
        log "INFO" "Created security chain: $CHAIN_NAME"
    fi
    
    # Link to DOCKER-USER if it exists, otherwise use INPUT
    if iptables -L DOCKER-USER -n >/dev/null 2>&1; then
        if ! iptables -C DOCKER-USER -j "$CHAIN_NAME" 2>/dev/null; then
            iptables -I DOCKER-USER -j "$CHAIN_NAME"
            log "INFO" "Linked security chain to DOCKER-USER"
        fi
    else
        if ! iptables -C INPUT -j "$CHAIN_NAME" 2>/dev/null; then
            iptables -I INPUT -j "$CHAIN_NAME"
            log "INFO" "Linked security chain to INPUT"
        fi
    fi
}

# Count currently blocked IPs
count_blocked_ips() {
    iptables -L "$CHAIN_NAME" -n 2>/dev/null | grep -c "DROP" || echo "0"
}

# Check if IP is already blocked
is_ip_blocked() {
    local ip="$1"
    iptables -C "$CHAIN_NAME" -s "$ip" -j DROP 2>/dev/null
}

# Block IP address
block_ip() {
    local ip="$1"
    
    info "Processing block request for IP: $ip"
    
    # Validate IP format
    if ! validate_ip "$ip"; then
        error_exit "Invalid IP address format: $ip"
    fi
    
    # Check if it's a private IP
    if is_private_ip "$ip"; then
        error_exit "Cannot block private/reserved IP address: $ip"
    fi
    
    # Initialize security chain
    init_security_chain
    
    # Check if already blocked
    if is_ip_blocked "$ip"; then
        warn "IP $ip is already blocked"
        return 0
    fi
    
    # Check if we're approaching the limit
    local current_count
    current_count=$(count_blocked_ips)
    if [[ $current_count -ge $MAX_BLOCKED_IPS ]]; then
        error_exit "Maximum blocked IPs limit reached ($MAX_BLOCKED_IPS). Please review and clean up old rules."
    fi
    
    # Add the blocking rule
    if iptables -I "$CHAIN_NAME" -s "$ip" -j DROP; then
        success "Successfully blocked IP: $ip"
        log "SECURITY" "BLOCKED IP: $ip (Total blocked: $((current_count + 1)))"
        
        # Optional: Add comment to the rule for better tracking
        iptables -I "$CHAIN_NAME" -s "$ip" -j DROP -m comment --comment "Blocked by security system on $(date '+%Y-%m-%d')" 2>/dev/null || true
        
        return 0
    else
        error_exit "Failed to block IP: $ip"
    fi
}

# Unblock IP address (bonus feature)
unblock_ip() {
    local ip="$1"
    
    if ! validate_ip "$ip"; then
        error_exit "Invalid IP address format: $ip"
    fi
    
    if iptables -D "$CHAIN_NAME" -s "$ip" -j DROP 2>/dev/null; then
        success "Successfully unblocked IP: $ip"
        log "SECURITY" "UNBLOCKED IP: $ip"
    else
        warn "IP $ip was not blocked or rule not found"
    fi
}

# Show help
show_help() {
    cat << EOF
Usage: $SCRIPT_NAME <IP_ADDRESS> [OPTIONS]

DESCRIPTION:
    Professional IP blocking script using iptables with security features.

ARGUMENTS:
    IP_ADDRESS    The IP address to block (required)

OPTIONS:
    -u, --unblock    Unblock the specified IP address
    -l, --list       List all blocked IPs
    -s, --status     Show blocking statistics
    -h, --help       Show this help message

EXAMPLES:
    $SCRIPT_NAME 192.168.1.100
    $SCRIPT_NAME 10.0.0.1 --unblock
    $SCRIPT_NAME --list
    $SCRIPT_NAME --status

LOG FILE:
    $LOG_FILE
EOF
}

# List blocked IPs
list_blocked_ips() {
    info "Currently blocked IP addresses:"
    if iptables -L "$CHAIN_NAME" -n --line-numbers 2>/dev/null | grep DROP; then
        echo ""
    else
        echo "No IPs currently blocked."
    fi
}

# Show status
show_status() {
    local count
    count=$(count_blocked_ips)
    info "Security Status:"
    echo "  - Chain: $CHAIN_NAME"
    echo "  - Blocked IPs: $count/$MAX_BLOCKED_IPS"
    echo "  - Log file: $LOG_FILE"
}

# Main function
main() {
    # Check if iptables is available
    if ! command -v iptables >/dev/null 2>&1; then
        error_exit "iptables is not installed or not in PATH"
    fi
    
    # Check if ipcalc is available (for private IP checking)
    if ! command -v ipcalc >/dev/null 2>&1; then
        warn "ipcalc not found. Private IP checking may be limited."
    fi
    
    # Check root privileges
    check_root
    
    # Parse arguments
    case "${1:-}" in
        -h|--help)
            show_help
            exit 0
            ;;
        -l|--list)
            list_blocked_ips
            exit 0
            ;;
        -s|--status)
            show_status
            exit 0
            ;;
        "")
            error_exit "No IP address provided. Use -h for help."
            ;;
        *)
            local ip="$1"
            local action="${2:-block}"
            
            case "$action" in
                -u|--unblock)
                    unblock_ip "$ip"
                    ;;
                *)
                    block_ip "$ip"
                    ;;
            esac
            ;;
    esac
}

# Run main function with all arguments
main "$@"
