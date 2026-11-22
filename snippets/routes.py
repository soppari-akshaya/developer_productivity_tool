from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import CodeSnippet
from . import snippets_bp

@snippets_bp.route('/snippets')
@login_required
def list_snippets():
    lang_filter = request.args.get('lang', 'all')
    search_q = request.args.get('q', '').strip()

    query = CodeSnippet.query.filter_by(user_id=current_user.id)
    if lang_filter != 'all':
        query = query.filter_by(language=lang_filter)
    if search_q:
        query = query.filter(
            (CodeSnippet.title.ilike(f'%{search_q}%')) | 
            (CodeSnippet.tags.ilike(f'%{search_q}%')) |
            (CodeSnippet.description.ilike(f'%{search_q}%'))
        )

    snippets = query.order_by(CodeSnippet.is_favorite.desc(), CodeSnippet.updated_at.desc()).all()
    
    # Available languages in collection
    languages = ['javascript', 'python', 'java', 'html', 'css', 'sql', 'typescript', 'bash']

    return render_template(
        'snippets/list.html',
        page_title='Code Snippet Manager',
        snippets=snippets,
        languages=languages,
        lang_filter=lang_filter,
        search_q=search_q
    )

@snippets_bp.route('/snippets/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        language = request.form.get('language', 'javascript')
        code = request.form.get('code', '').strip()
        tags = request.form.get('tags', '').strip()
        is_favorite = 'is_favorite' in request.form

        if not title or not code:
            flash('Snippet title and code content are required.', 'danger')
            return redirect(url_for('snippets.create'))

        snippet = CodeSnippet(
            title=title,
            description=description,
            language=language,
            code=code,
            tags=tags,
            is_favorite=is_favorite,
            user_id=current_user.id
        )
        db.session.add(snippet)
        db.session.commit()
        flash('Code snippet saved to vault!', 'success')
        return redirect(url_for('snippets.list_snippets'))

    languages = ['javascript', 'python', 'java', 'html', 'css', 'sql', 'typescript', 'bash']
    initial_code = request.args.get('code', '')
    initial_lang = request.args.get('lang', 'javascript')
    return render_template(
        'snippets/create.html',
        page_title='Save New Code Snippet',
        languages=languages,
        initial_code=initial_code,
        initial_lang=initial_lang
    )

@snippets_bp.route('/snippets/<int:snippet_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(snippet_id):
    snippet = db.get_or_404(CodeSnippet, snippet_id)
    if snippet.user_id != current_user.id:
        flash('Unauthorized to edit this snippet.', 'danger')
        return redirect(url_for('snippets.list_snippets'))

    if request.method == 'POST':
        snippet.title = request.form.get('title', snippet.title).strip()
        snippet.description = request.form.get('description', snippet.description).strip()
        snippet.language = request.form.get('language', snippet.language)
        snippet.code = request.form.get('code', snippet.code).strip()
        snippet.tags = request.form.get('tags', snippet.tags).strip()
        snippet.is_favorite = 'is_favorite' in request.form
        snippet.updated_at = datetime.utcnow()

        db.session.commit()
        flash('Snippet updated.', 'success')
        return redirect(url_for('snippets.list_snippets'))

    languages = ['javascript', 'python', 'java', 'html', 'css', 'sql', 'typescript', 'bash']
    return render_template('snippets/edit.html', page_title=f'Edit {snippet.title}', snippet=snippet, languages=languages)

@snippets_bp.route('/snippets/<int:snippet_id>/toggle-favorite', methods=['POST'])
@login_required
def toggle_favorite(snippet_id):
    snippet = db.get_or_404(CodeSnippet, snippet_id)
    if snippet.user_id == current_user.id:
        snippet.is_favorite = not snippet.is_favorite
        db.session.commit()
    return redirect(request.referrer or url_for('snippets.list_snippets'))

@snippets_bp.route('/snippets/<int:snippet_id>/delete', methods=['POST'])
@login_required
def delete(snippet_id):
    snippet = db.get_or_404(CodeSnippet, snippet_id)
    if snippet.user_id == current_user.id:
        db.session.delete(snippet)
        db.session.commit()
        flash('Snippet removed from vault.', 'info')
    return redirect(url_for('snippets.list_snippets'))

