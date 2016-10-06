import StringIO

from fabric.api import env, put, roles, runs_once, sudo, task
from fabric.operations import prompt
from fabric.tasks import execute

from jinja2 import Template

import app


env['eagerly_disconnect'] = True


APPLICATIONS = ['static', 'frontend']
CAMPAIGN_CLASSES = ['red', 'black', 'green']


def validate_classes(campaign_class):
    """Checks that the campaign class is valid"""
    if campaign_class in CAMPAIGN_CLASSES:
        return campaign_class
    raise Exception("Invalid class {}, valid values are {}".format(campaign_class, CAMPAIGN_CLASSES))


@runs_once
def set_context():
    env['context'] = {
        'heading': prompt("Heading:", 'heading'),
        'extra_info': prompt("Short description:", 'extra_info'),
        'more_info_url': prompt("More info link:", 'more_info_url'),
        'campaign_class': prompt("Campaign class (one of {}):".format(", ".join(CAMPAIGN_CLASSES)), 'campaign_class', validate=validate_classes)
    }


def template(app):
    if app == 'frontend':
        template = Template("""<div id="campaign" class="{{ campaign_class }}">
    <div class="campaign-inner">
      <h1>{{ heading|e }}</h1>
      <p>{{ extra_info|e }}</p>

      {% if more_info_url %}
        <a href="{{ more_info_url|e }}">More information</a>
      {% endif %}
    </div>
  </div>""")
    elif app == 'static':
        template = Template("""<p>{{ heading|e }}<br />
    {{ extra_info|e }}</p>
      {% if more_info_url %}
        <a href="{{ more_info_url|e }}" class="more-information">More information</a>
      {% endif %}""")

    env['template_contents'] = template.render(env.context)


def clear_static_generated_templates():
    """
    Our various frontend applications use the wrapper.html.erb,
    header_footer_only.html.erb and core_layout.html.erb layout templates.
    They get these templates using the Slimmer gem, which fetches
    these templates from the static application, located using ASSET_ROOT.

    When static is deployed there are no generated layout templates
    on static At the first request to one these, static will generate
    the template. The template will be placed in the public/template
    directory. From that point on, the templates are served by nginx.

    This function clears the public/template directory to force it to
    be regenerated to include the emergency campaign.
    """
    for template in ('wrapper.html.erb', 'header_footer_only.html.erb', 'core_layout.html.erb'):
        sudo('rm /var/apps/static/public/templates/{}'.format(template))


def deploy_banner(application):
    execute(template, application)
    if application == 'frontend':
        remote_filename = '/var/apps/frontend/app/views/homepage/_campaign_notification.html.erb'
    elif application == 'static':
        remote_filename = "/var/apps/static/app/views/notifications/banner_{}.erb".format(env.campaign_class)
    content = env['template_contents']
    put(StringIO.StringIO(content), remote_filename, use_sudo=True, mirror_local_mode=True)
    sudo('chown deploy:deploy %s' % remote_filename)
    execute(app.restart, application)
    if application == 'static':
        clear_static_generated_templates()


def remove_banner(application):
    if application == 'frontend':
        remote_filenames = ['/var/apps/frontend/app/views/homepage/_campaign_notification.html.erb']
    elif application == 'static':
        remote_filenames = ["/var/apps/static/app/views/notifications/banner_%s.erb" % i for i in CAMPAIGN_CLASSES]
    content = ''
    for remote_filename in remote_filenames:
        put(StringIO.StringIO(content), remote_filename, use_sudo=True, mirror_local_mode=True)
        sudo('chown deploy:deploy %s' % remote_filename)
    execute(app.restart, application)
    if application == 'static':
        clear_static_generated_templates()


@task
@roles('class-frontend')
def deploy_emergency_banner():
    """Deploy an emergency banner to GOV.UK"""
    execute(set_context)
    for application in APPLICATIONS:
        deploy_banner(application)


@task
@roles('class-frontend')
def remove_emergency_banner():
    """Remove all banners from GOV.UK"""
    for application in APPLICATIONS:
        remove_banner(application)
