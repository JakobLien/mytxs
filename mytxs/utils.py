def disableForm(form):
    """Disable alle fields i formet (untatt id, for da funke det ikkje på modelformsets)"""
    for name, field in form.fields.items():
        if name != 'id':
            field.disabled = True