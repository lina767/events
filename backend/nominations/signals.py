import django.dispatch

# Sent once per resolved nominee when a nomination (or bundle of duplicate
# nominations for the same nominee) is approved. providing_args:
# nomination, event, nominee. The invitations app listens for this to send
# the initial invitation - see invitations.signals.
nomination_approved = django.dispatch.Signal()
