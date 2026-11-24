// AppDelegate.m
#import "AppDelegate.h"
#import "IrisTheme.h"
#import "IrisData.h"

// Forward declare view controllers
@interface IrisFeedViewController : UIViewController
@end

@interface IrisExploreViewController : UIViewController
@end

@interface IrisCreateViewController : UIViewController
@end

@interface IrisActivityViewController : UIViewController
@end

@interface IrisProfileViewController : UIViewController
- (instancetype)initWithUsername:(NSString *)username;
@end

@implementation AppDelegate

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    self.window = [[UIWindow alloc] initWithFrame:[[UIScreen mainScreen] bounds]];
    self.window.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // Initialize centralized mock data
    [IrisData sharedData];
    
    // Create 5 primary screen controllers
    IrisFeedViewController *feedVC = [[IrisFeedViewController alloc] init];
    IrisExploreViewController *exploreVC = [[IrisExploreViewController alloc] init];
    IrisCreateViewController *createVC = [[IrisCreateViewController alloc] init];
    IrisActivityViewController *activityVC = [[IrisActivityViewController alloc] init];
    IrisProfileViewController *profileVC = [[IrisProfileViewController alloc] initWithUsername:[[IrisData sharedData].currentUserProfile username]];
    
    NSArray *controllers = @[feedVC, exploreVC, createVC, activityVC, profileVC];
    self.tabBarController = [[IrisTabBarController alloc] initWithViewControllers:controllers];
    
    self.window.rootViewController = self.tabBarController;
    [self.window makeKeyAndVisible];
    
    return YES;
}

- (BOOL)application:(UIApplication *)app openURL:(NSURL *)url options:(NSDictionary<UIApplicationOpenURLOptionsKey,id> *)options {
    // Handle iris:// URL scheme
    if ([[url scheme] isEqualToString:@"iris"]) {
        NSString *host = [url host];
        if ([host isEqualToString:@"explore"]) {
            [self.tabBarController switchToTab:IrisTabItemExplore];
        } else if ([host isEqualToString:@"create"]) {
            [self.tabBarController switchToTab:IrisTabItemCreate];
        } else if ([host isEqualToString:@"activity"]) {
            [self.tabBarController switchToTab:IrisTabItemActivity];
        } else if ([host isEqualToString:@"profile"]) {
            [self.tabBarController switchToTab:IrisTabItemProfile];
        } else {
            [self.tabBarController switchToTab:IrisTabItemHome];
        }
        return YES;
    }
    return NO;
}

@end
