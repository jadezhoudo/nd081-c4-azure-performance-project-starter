from flask import Flask, request, render_template
import os
import random
import redis
import socket
import sys
import logging
from datetime import datetime

# App Insights
from opencensus.ext.azure.log_exporter import AzureLogHandler, AzureEventHandler
from opencensus.ext.azure import metrics_exporter
from opencensus.stats import (
    aggregation as aggregation_module,
    measure as measure_module,
    stats as stats_module,
    view as view_module,
)
from opencensus.tags import tag_map as tag_map_module
from opencensus.trace import config_integration
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.flask.flask_middleware import FlaskMiddleware

# Logging
config_integration.trace_integrations(['logging'])
config_integration.trace_integrations(['requests'])
logger = logging.getLogger(__name__)

handler = AzureLogHandler(
    connection_string='InstrumentationKey=7f038c7f-8576-4eb0-8348-99b8f1c4f153;'
                      'IngestionEndpoint=https://westus-0.in.applicationinsights.azure.com/;'
                      'LiveEndpoint=https://westus.livediagnostics.monitor.azure.com/'
)
handler.setFormatter(logging.Formatter('%(traceId)s %(spanId)s %(message)s'))
logger.addHandler(handler)

logger.addHandler(AzureEventHandler(
    connection_string='InstrumentationKey=7f038c7f-8576-4eb0-8348-99b8f1c4f153;'
                      'IngestionEndpoint=https://westus-0.in.applicationinsights.azure.com/;'
                      'LiveEndpoint=https://westus.livediagnostics.monitor.azure.com/')
                  )
logger.setLevel(logging.INFO)

stats = stats_module.stats
view_manager = stats.view_manager

# Metrics
exporter = metrics_exporter.new_metrics_exporter(
    enable_standard_metrics=True,
    connection_string='InstrumentationKey=7f038c7f-8576-4eb0-8348-99b8f1c4f153;'
                      'IngestionEndpoint=https://westus-0.in.applicationinsights.azure.com/;'
                      'LiveEndpoint=https://westus.livediagnostics.monitor.azure.com/'
)

view_manager.register_exporter(exporter)

# Tracing
tracer = Tracer(
    exporter=AzureExporter(
        connection_string='InstrumentationKey=7f038c7f-8576-4eb0-8348-99b8f1c4f153;'
                          'IngestionEndpoint=https://westus-0.in.applicationinsights.azure.com/;'
                          'LiveEndpoint=https://westus.livediagnostics.monitor.azure.com/'),
    sampler=ProbabilitySampler(1.0),
)

app = Flask(__name__)

# Requests
middleware = FlaskMiddleware(
    app,
    exporter=AzureExporter(
        connection_string="InstrumentationKey=7f038c7f-8576-4eb0-8348-99b8f1c4f153;"
                          "IngestionEndpoint=https://westus-0.in.applicationinsights.azure.com/;"
                          "LiveEndpoint=https://westus.livediagnostics.monitor.azure.com/"),
    sampler=ProbabilitySampler(rate=1.0)
)

# Load configurations from environment or config file
app.config.from_pyfile('config_file.cfg')

button1 = os.environ.get('VOTE1VALUE', app.config['VOTE1VALUE'])
button2 = os.environ.get('VOTE2VALUE', app.config['VOTE2VALUE'])
title = os.environ.get('TITLE', app.config['TITLE'])

# Redis Connection
r = redis.Redis()

# Change title to host name to demo NLB
if app.config['SHOWHOST'] == "true":
    title = socket.gethostname()

# Init Redis
if not r.get(button1):
    r.set(button1, 0)
if not r.get(button2):
    r.set(button2, 0)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        # Get current values
        vote1 = r.get(button1).decode('utf-8')
        with tracer.span(name="Cats Vote"):
            print("Cats Vote")

        vote2 = r.get(button2).decode('utf-8')
        with tracer.span(name="Dogs Vote"):
            print("Dogs Vote")

        # Return index with values
        return render_template("index.html", value1=int(vote1), value2=int(vote2),
                               button1=button1, button2=button2, title=title)

    elif request.method == 'POST':
        if request.form['vote'] == 'reset':
            # Empty table and return results
            r.set(button1, 0)
            r.set(button2, 0)
            vote1 = r.get(button1).decode('utf-8')
            properties = {'custom_dimensions': {'Cats Vote': vote1}}
            logger.info("Cats Vote", extra=properties)

            vote2 = r.get(button2).decode('utf-8')
            properties = {'custom_dimensions': {'Dogs Vote': vote2}}
            logger.info("Dogs Vote", extra=properties)

            return render_template("index.html", value1=int(vote1), value2=int(vote2),
                                   button1=button1, button2=button2, title=title)

        else:
            # Insert vote result into DB
            vote = request.form['vote']
            r.incr(vote, 1)

            # Get current values
            vote1 = r.get(button1).decode('utf-8')
            vote2 = r.get(button2).decode('utf-8')

            # Return results
            return render_template("index.html", value1=int(vote1), value2=int(vote2),
                                   button1=button1, button2=button2, title=title)


if __name__ == "__main__":
    # TODO: Use the statement below when running locally
    # app.run()
    # TODO: Use the statement below before deployment to VMSS
    app.run(host='0.0.0.0', threaded=True, debug=True)  # remote
