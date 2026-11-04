#!/bin/sh
# Imports the version-controlled workflows and activates the triggerable ones. Runs once before n8n starts.
# Z (error handler) stays inactive: n8n runs error workflows without activation.
set -e
n8n import:workflow --separate --input=/workflows
for id in OrkA0CustomerIntk OrkB0IncidentEscl OrkC0RfpProcessng OrkD0DeadlineMntr OrkE0ApprovalAudt; do
  n8n update:workflow --id=$id --active=true
done
n8n update:workflow --id=OrkZ0ErrorHandler --active=false
echo "Axiomera workflows imported and activated"
