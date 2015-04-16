# compatipede plug-ins

To make it trivial to throw in new tests, we have a JSON-based plug-in feature.

Plug-ins live in the "plugins" folder. They are loaded by scanning this folder for .json - files each time the view.py script runs.

A plug-in looks much like this:

```
{
    "name": "window-orientation-usage",
    "javascript": "window.__defineGetter__('orientation', function(){console.log('window.orientation used')});",
    "injectionTime": "start",
    "dataSource": "console",
    "dataRegexp": "window\.orientation used",
    "bug": "123456",
    "targetSite": "",
    "markMatchesAs": "fail",
    "dataType":"json"
}
```

## Property definitions:

* `name` uniquely identifies this plug-in. If two plug-ins have the same name, an error is thrown. It is recommended to make the name of the plugin.json file equal the name of the plug-in. Caveat: if data gets stored to a MongoDB, the name should not contain any period (.) characters.

* `javascript` is a string of JS that will be injected into the page.

* `injectionTime` controls when the injected JS will run. It takes values "start" or "load" ("start" being ASAP - before any page JS runs, "load" being when the load event would fire). It can also be set to "resource_scan" to indicate that the regexp shall be matched against all included JS and CSS files.

* `dataSource` tells the framework where to read the javascript output. It can be set to "console" or "returnValue". If it's "returnValue" the injected JS needs to evaluate to something other than "undefined" to get anythong logged.

* `dataRegexp` only needs setting if the dataSource is "console" - anything that matches the regexp will be logged to the database tagged with the site and the "plug-in"'s name. So outcome of this might be:

    ```
    "example.com": {
       "window-orientation-usage" : "window.orientation used",
    }
    ```

* `bug` is a reference to some bug this test is relevant for. This value, if set, is just passed through to the results log.

* `targetSite` can limit the test to be applied on a specific site only. The value will be compared strictly (no wildcards supported) against the hostname of a site. If it's empty or not set, the plug-in runs everywhere.

* `regexp`, if set, is the regular expression all CSS and JS will be matched against.

* `comment` can be a description of the plugin or expected results. At some point, we may want systems that add comments to bugs automatically, the comment property should be suitable as a bug description or annotation.

* `markMatchesAs`, if set, lets the plugin set a final pass/fail status for the website. The value can be either "pass" or "fail". If multiple plugins with markMatchesAs all run on a given website and end up disagreeing, "fail" will win.

* `dataType` can be set to `json` to make the script parse the returned data as JSON.

Another example of a potential plugin, say we find a generic problem with a common script - for example jQuery 1.6:

```
{
    "name": "jQuery-1-6-check",
    "javascript": "try{ jQuery.fn.jquery === "1.6" }catch(e){}",
    "injectionTime": "load",
    "dataSource": "returnValue",
    "bug": "123456"
}
```

So this JS evaluates to true if site runs jQuery 1.6, returns nothing (well, undefined) otherwise. Outcome might be:

```
{ 
  "example.com": {
    "jQuery-1-6-check" : "true",
    ...
}
```
