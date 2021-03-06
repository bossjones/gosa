/**
 * Reads and evaluates actions (e.g. "change password").
 */
qx.Class.define("gosa.engine.extensions.Actions", {
  extend : qx.core.Object,

  implement : [gosa.engine.extensions.IExtension],

  members : {

    process : function(data, target, context) {
      qx.core.Assert.assertArray(data, "Actions configuration must be an array");
      data.forEach(function(action) {
        if (this._isActionAllowed(action)) {  // actions without permission are not shown
          this._processAction(action, target, context);
        }
      }, this);
    },

    /**
     * Checks if the user has the permission to execute the action.
     *
     * @param action {Map} The action node
     * @return {Boolean}
     */
    _isActionAllowed : function(action) {
      qx.core.Assert.assertMap(action);
      qx.core.Assert.assertTrue(action.hasOwnProperty("dialog") || action.hasOwnProperty("target"));

      // check target
      if (action.hasOwnProperty("target")) {
        qx.core.Assert.assertString(action.target);
        var methodName = /^([^(]+)\((.*)\)$/.exec(action.target)[1];
        qx.core.Assert.assertString(methodName);
        qx.core.Assert.assertFalse(methodName === "");

        if (!gosa.Session.getInstance().isCommandAllowed(methodName)) {
          return false;
        }
      }

      // check dialog
      if (action.hasOwnProperty("dialog")) {
        qx.core.Assert.assertString(action.dialog);
        gosa.util.Template.getDialogRpc(action.dialog);
        var clazz = gosa.ui.dialogs.actions[action.dialog];
        var rpcList = clazz.RPC_CALLS;
        var session = gosa.Session.getInstance();

        // user must be allowed to enhance each rpc
        return rpcList.every(session.isCommandAllowed, session);
      }

      return true;
    },

    _processAction : function(data, target, context) {
      qx.core.Assert.assertMap(data, "Action configuration must be a hash map");
      qx.core.Assert.assertKeyInMap("name", data, "Action configuration must have the key 'name'");
      qx.core.Assert.assertKeyInMap("text", data, "Action configuration must have the key 'text'");

      // shortcut
      var command = null;
      if (data.hasOwnProperty("shortcut")) {
        command = new qx.ui.command.Command(data.shortcut);
      }

      // button creation
      var button = new qx.ui.menu.Button(data.text, context.getResourceManager().getResource(data.icon), command);
      button.setAppearance("icon-menu-button");

      // condition
      if (data.hasOwnProperty("condition")) {
        button.addListenerOnce("appear", function() {
          this._checkCondition(data.condition, context).then(function(result) {
            button.setEnabled(result);
          });
        }, this);
      }

      // listener to open dialog
      if (data.hasOwnProperty("dialog")) {
        button.addListener("execute", function() {
          var clazz = qx.Class.getByName("gosa.ui.dialogs.actions." + data.dialog);
          if (!clazz) {
            qx.core.Assert.fail("Cannot find class for dialog '" + data.dialog + "'");
          }
          var dialog = new clazz(context.getActionController());
          dialog.setAutoDispose(true);

          if (data.hasOwnProperty("icon")) {
            dialog.setIcon(context.getResourceManager().getResource(data.icon));
          }
          dialog.open();
        });
      }

      // listener to invoke target
      if (data.hasOwnProperty("target")) {
        this._addExecuteTargetListener(data.target, button, context);
      }

      context.addActionMenuEntry(data.name, button);
    },

    /**
     * Check if the given condition is satisfied.
     *
     * @param condition {String} Complete condition string as saved in the template
     * @param context {gosa.engine.Context}
     */
    _checkCondition : function(condition, context) {
      qx.core.Assert.assertString(condition);

      // get configuration for condition rpc
      var parser = /^(!)?([^(]*)(\((.*)\))?$/;
      var parsed = parser.exec(condition);
      var name = parsed[2];
      var negated = parsed[1] === "!";
      var result = false;

      // conditions with arguments are rpc; all others are attributes of the object
      if (parsed[4]) {  // has arguments
        // method call

        // build arguments for rpc call
        var args = [];
        parsed[4].split(",").forEach(function(arg) {
          if (arg === "dn") {
            args.push(context.getActionController().getDn());
          }
          else if (arg === "uuid") {
            args.push(context.getActionController().getUuid());
          }
          else if (arg[0] === '"' || arg[0] === "'") {  // argument is a static string
            args.push(arg.replace(/^["']/, "").replace(/["']$/, ""));
          }
          else {  // attributes of object
            var value = context.getAttributeValue(arg);
            args.push(value && value.getLength() > 0 ? value.getItem(0) : null);
          }
        });

        // invoke rpc
        var rpc = gosa.io.Rpc.getInstance();
        return rpc.cA.apply(rpc, [name].concat(args))
        .then(function(result) {
          // negation
          if (negated) {
            result = !result;
          }
          return result;
        }, this)
        .catch(function(error) {
          new gosa.ui.dialogs.Error(error.message).open();
        });
      }
      else {
        // object attribute
        var value = context.getActionController().getAttributeValue(name);
        if (value.getLength() > 0) {
          result = !!value.getItem(0);
        }

        // negation
        if (negated) {
          result = !result;
        }

        return qx.Promise.resolve(result);
      }
    },

    /**
     * Executes a given method (aka target) on the object.
     *
     * @param target {String} The unparsed target string as it apperas in the template
     * @param button {qx.ui.menu.Button} Button on which the listener shall be added
     * @param context {gosa.engine.Context}
     */
    _addExecuteTargetListener : function(target, button, context) {
      qx.core.Assert.assertString(target);
      qx.core.Assert.assertInstance(button, qx.ui.menu.Button);

      var parser = /^([^(]+)\((.*)\)$/;
      var parsed = parser.exec(target);
      var methodName = parsed[1];
      var params = parsed[2];
      var args = [];

      // create argument list
      if (qx.lang.Type.isString(params) && params !== "") {
        params = params.split(",");
        var paramParser = /%\(([^)]+)\)s/;

        params.forEach(function(param) {
          var match = paramParser.exec(param);
          if (match) {
            var data = context.getActionController().getProperty(match[1]);
            if (qx.lang.Type.isArray(data)) {
              args.push(param.replace(match[0], data[0]));
            }
            else {
              args.push(param.replace(match[0], data));
            }
          }
        });
      }

      // listener for invoking the target
      button.addListener("execute", function() {
        args.unshift(methodName);
        context.getActionController().callMethod.apply(context.getActionController(), args)
        .then(function(result) {
          qx.log.Logger.info("Call of method '" + methodName + "' was successful and returned '" + result + "'");
        })
        .catch(function(error) {
          new gosa.ui.dialogs.Error(error.message).open();
        });
      }, this);
    }
  },

  defer : function() {
    gosa.engine.ExtensionManager.getInstance().registerExtension("actions", gosa.engine.extensions.Actions);
  }
});
